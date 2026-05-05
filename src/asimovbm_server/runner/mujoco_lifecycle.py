"""WebSocket lifecycle backed by a server-owned MuJoCo simulation."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import WebSocket

from asimovbm_protocol import (
    FailureCategory,
    FailureMessage,
    TerminalMessage,
    TerminalStatus,
    to_payload,
)

from ..sessions import Session, SessionManager, SessionState
from ..simulation import MuJoCoAdapterConfig, MuJoCoSimulationAdapter, SimulationSetupError
from .lifecycle import _CLIENT_FAILURE_SENTINEL, LifecycleResult, ScriptedLifecycleOrchestrator


class MuJoCoLifecycleOrchestrator(ScriptedLifecycleOrchestrator):
    """Drive the benchmark lifecycle from a participant-submitted MJCF model."""

    def __init__(
        self,
        manager: SessionManager | None = None,
        *,
        package_root: Path,
        max_steps: int = 20,
        control_dt: float = 0.05,
        goal: tuple[float, float] = (1.0, 0.0),
        package_timeout_s: float = 5.0,
        trace_messages: bool = False,
    ) -> None:
        super().__init__(manager, [], trace_messages=trace_messages)
        self._package_root = package_root.resolve()
        self._max_steps = max_steps
        self._control_dt = control_dt
        self._goal = goal
        self._package_timeout_s = package_timeout_s
        self.last_adapter: MuJoCoSimulationAdapter | None = None

    async def run(self, session: Session, websocket: WebSocket) -> None:
        if self._manager is None:
            self._manager = websocket.app.state.session_manager
        result = LifecycleResult()
        self.last_result = result

        if not await self._bootstrap(session, websocket):
            return

        try:
            package = await self._wait_for_package(session)
            model_path = self._resolve_model_path(package.model.get("path"))
            adapter = MuJoCoSimulationAdapter(
                MuJoCoAdapterConfig(
                    model_path=model_path,
                    max_steps=self._max_steps,
                    control_dt=self._control_dt,
                    goal=self._goal,
                    action_mapping=dict(package.action_mapping),
                )
            )
        except SimulationSetupError as exc:
            await self._terminal_with_failure(websocket, session, result, str(exc))
            return

        self.last_adapter = adapter
        action_size = self._action_size(session)
        while not adapter.terminal:
            step = adapter.next_step()
            self._trace_step(step)
            await self._send_json(websocket, {"type": "step", "data": to_payload(step)})

            try:
                accepted = await self._receive_action_with_resync(
                    websocket=websocket,
                    session=session,
                    expected_step_id=step.step_id,
                    expected_length=action_size,
                    result=result,
                )
            except Exception:
                raise

            if accepted is None:
                return
            if accepted is _CLIENT_FAILURE_SENTINEL:
                break

            try:
                adapter.apply_action(accepted)
            except Exception as exc:
                result.failures.append(
                    FailureMessage(
                        category=FailureCategory.INVALID_ACTION,
                        summary=str(exc),
                        step_id=accepted.step_id,
                    )
                )
                break

        report_ref = self._manager.make_report_ref()
        report_payload = adapter.smoke_result().to_report_context()
        report_payload["actions_recorded"] = len(result.actions_received)
        websocket.app.state.reports[report_ref] = report_payload
        self._manager.finalize(session, report_ref=report_ref)
        terminal = TerminalMessage(
            status=TerminalStatus.REPORT_READY if not result.failures else TerminalStatus.FAILED,
            report_ref=report_ref,
            failures=list(result.failures),
        )
        result.terminal = terminal
        await self._send_json(websocket, {"type": "terminal", "data": to_payload(terminal)})

    async def _bootstrap(self, session: Session, websocket: WebSocket) -> bool:
        try:
            first = await websocket.receive_json()
        except Exception:
            return False
        self._trace("<-", first)
        if first.get("type") != "bootstrap":
            await self._fatal(websocket, "compatibility", "expected bootstrap message")
            return False

        from asimovbm_protocol import PROTOCOL_VERSION
        from asimovbm_protocol.adapters import session_bootstrap_adapter

        try:
            bootstrap = session_bootstrap_adapter.validate_python(first.get("data", {}))
        except Exception as exc:
            await self._fatal(websocket, "compatibility", f"malformed bootstrap: {exc}")
            return False
        if bootstrap.protocol_version != PROTOCOL_VERSION:
            await self._fatal(
                websocket,
                "compatibility",
                f"unsupported protocol_version {bootstrap.protocol_version!r}",
            )
            return False
        await self._send_json(
            websocket,
            {"type": "bootstrap_ack", "data": {"protocol_version": PROTOCOL_VERSION}},
        )
        return True

    async def _wait_for_package(self, session: Session):
        deadline = asyncio.get_running_loop().time() + self._package_timeout_s
        while asyncio.get_running_loop().time() < deadline:
            if session.state == SessionState.PACKAGE_REJECTED:
                raise SimulationSetupError("submitted package was rejected")
            if session.package is not None and session.validation is not None:
                if session.validation.accepted:
                    return session.package
                raise SimulationSetupError("submitted package was rejected")
            await asyncio.sleep(0.01)
        raise SimulationSetupError("timed out waiting for package submission")

    def _resolve_model_path(self, raw_path: object) -> Path:
        if not isinstance(raw_path, str) or not raw_path:
            raise SimulationSetupError("package model.path must be a non-empty relative path")
        candidate = Path(raw_path)
        if candidate.is_absolute():
            raise SimulationSetupError("package model.path must be relative")
        resolved = (self._package_root / candidate).resolve()
        if self._package_root != resolved and self._package_root not in resolved.parents:
            raise SimulationSetupError("package model.path escapes package root")
        return resolved

    async def _terminal_with_failure(
        self,
        websocket: WebSocket,
        session: Session,
        result: LifecycleResult,
        summary: str,
    ) -> None:
        failure = FailureMessage(category=FailureCategory.SETUP, summary=summary)
        result.failures.append(failure)
        report_ref = self._manager.make_report_ref()
        websocket.app.state.reports[report_ref] = {
            "maturity": "mujoco_setup_failed",
            "status": "failed",
            "summary": summary,
        }
        self._manager.finalize(session, report_ref=report_ref)
        terminal = TerminalMessage(
            status=TerminalStatus.FAILED,
            report_ref=report_ref,
            failures=[failure],
        )
        result.terminal = terminal
        await self._send_json(websocket, {"type": "terminal", "data": to_payload(terminal)})

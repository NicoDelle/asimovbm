"""Server-side WebSocket lifecycle orchestrator.

The orchestrator drives the bootstrap → control-loop → terminal exchange
on the server's WebSocket route. Step messages come from a configurable
sequence (real simulation step sources arrive in Unit 5/6); for Unit 4
this is a pre-determined script so transport-level behavior can be tested
independently of any simulation backend.
"""

from __future__ import annotations

import asyncio
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect, status

from asimovbm_protocol import (
    PROTOCOL_VERSION,
    ActionMessage,
    FailureCategory,
    FailureMessage,
    StepMessage,
    TerminalMessage,
    TerminalStatus,
    to_payload,
)
from asimovbm_protocol.adapters import (
    action_message_adapter,
    session_bootstrap_adapter,
)

from ..sessions import Session, SessionManager


@dataclass
class LifecycleResult:
    actions_received: list[ActionMessage] = field(default_factory=list)
    failures: list[FailureMessage] = field(default_factory=list)
    terminal: TerminalMessage | None = None


def validate_action_payload(
    action: ActionMessage,
    *,
    expected_step_id: int,
    expected_length: int | None,
    joint_bounds: Sequence[tuple[float, float]] | None = None,
) -> str | None:
    """Return ``None`` when the action is valid, else a human-readable reason.

    Enforces:

    - matching ``step_id``
    - finite floats (no NaN/Inf)
    - exact length matching ``expected_length`` (when provided)
    - per-joint bounds when ``joint_bounds`` is provided
    """
    if action.step_id != expected_step_id:
        return (
            f"stale or wrong step_id (expected {expected_step_id}, "
            f"got {action.step_id})"
        )
    for index, value in enumerate(action.action):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return f"action[{index}] is not a JSON number"
        if not math.isfinite(value):
            return f"action[{index}] is not finite"
    if expected_length is not None and len(action.action) != expected_length:
        return (
            f"action length {len(action.action)} does not match "
            f"declared joints length {expected_length}"
        )
    if joint_bounds is not None:
        for index, (low, high) in enumerate(joint_bounds):
            if index >= len(action.action):
                break
            value = action.action[index]
            if value < low or value > high:
                return (
                    f"action[{index}]={value} outside configured bounds [{low}, {high}]"
                )
    return None


def validate_raw_action_payload(payload: object) -> str | None:
    """Validate action-vector JSON types before Pydantic coercion.

    The protocol adapters intentionally accept dataclasses at Python
    boundaries, but the network boundary must be stricter: an action vector
    item sent as ``"0.0"`` is not a JSON number even though Pydantic could
    coerce it into a float. Check the raw payload first so simulation never
    sees coerced participant input.
    """
    if not isinstance(payload, dict):
        return "action payload must be an object"
    values = payload.get("action")
    if not isinstance(values, list):
        return "action must be a JSON array"
    for index, value in enumerate(values):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return f"action[{index}] is not a JSON number"
        if not math.isfinite(value):
            return f"action[{index}] is not finite"
    return None


class ScriptedLifecycleOrchestrator:
    """Drives the WS lifecycle from a fixed sequence of ``StepMessage`` values.

    Real simulation orchestrators replace this in Unit 6. The contract this
    class enforces — bootstrap ack, action validation, opaque terminal
    report ref — is what the network transport tests rely on.
    """

    def __init__(
        self,
        manager: SessionManager,
        steps: Sequence[StepMessage],
        *,
        terminal_status: TerminalStatus = TerminalStatus.REPORT_READY,
        report_factory: Callable[[Session], dict[str, Any]] | None = None,
        delay_before_step_id: dict[int, float] | None = None,
        joint_bounds: Sequence[tuple[float, float]] | None = None,
    ):
        self._manager = manager
        self._steps = list(steps)
        self._terminal_status = terminal_status
        self._report_factory = report_factory or (
            lambda session: {
                "status": "ok",
                "maturity": "fake_protocol",
                "actions_recorded": 0,
            }
        )
        self._delay_before_step_id = dict(delay_before_step_id or {})
        self._joint_bounds = joint_bounds
        # Last-run telemetry, exposed for tests.
        self.last_result: LifecycleResult | None = None

    async def run(self, session: Session, websocket: WebSocket) -> None:
        result = LifecycleResult()
        self.last_result = result

        # 1. bootstrap exchange ------------------------------------------
        try:
            first = await websocket.receive_json()
        except WebSocketDisconnect:
            return
        if first.get("type") != "bootstrap":
            await self._fatal(websocket, "compatibility", "expected bootstrap message")
            return
        try:
            bootstrap = session_bootstrap_adapter.validate_python(first.get("data", {}))
        except Exception as exc:
            await self._fatal(
                websocket, "compatibility", f"malformed bootstrap: {exc}"
            )
            return
        if bootstrap.protocol_version != PROTOCOL_VERSION:
            await self._fatal(
                websocket,
                "compatibility",
                f"unsupported protocol_version {bootstrap.protocol_version!r}",
            )
            return
        await websocket.send_json(
            {
                "type": "bootstrap_ack",
                "data": {"protocol_version": PROTOCOL_VERSION},
            }
        )

        # 2. control loop -------------------------------------------------
        action_size = self._action_size(session)
        for step in self._steps:
            delay = self._delay_before_step_id.get(step.step_id)
            if delay:
                await asyncio.sleep(delay)
            await websocket.send_json({"type": "step", "data": to_payload(step)})

            try:
                accepted = await self._receive_action_with_resync(
                    websocket=websocket,
                    session=session,
                    expected_step_id=step.step_id,
                    expected_length=action_size,
                    result=result,
                )
            except WebSocketDisconnect:
                return
            if accepted is None:
                # too many invalid messages; orchestrator already closed
                return
            if accepted is _CLIENT_FAILURE_SENTINEL:
                # client gave up on this step; record and end episode
                break

        # 3. terminal -----------------------------------------------------
        report_ref = self._manager.make_report_ref()
        report_payload = self._report_factory(session)
        report_payload.setdefault("actions_recorded", len(result.actions_received))
        websocket.app.state.reports[report_ref] = report_payload
        self._manager.finalize(session, report_ref=report_ref)
        terminal = TerminalMessage(
            status=self._terminal_status,
            report_ref=report_ref,
            failures=list(result.failures),
        )
        result.terminal = terminal
        await websocket.send_json({"type": "terminal", "data": to_payload(terminal)})

    # --- helpers --------------------------------------------------------

    async def _fatal(
        self, websocket: WebSocket, category: str, summary: str
    ) -> None:
        try:
            await websocket.send_json(
                {"type": "error", "category": category, "summary": summary}
            )
        finally:
            await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)

    def _action_size(self, session: Session) -> int | None:
        if session.package is None:
            return None
        action_mapping = session.package.action_mapping
        if not isinstance(action_mapping, dict):
            return None
        joints = action_mapping.get("joints")
        if isinstance(joints, list):
            return len(joints)
        return None

    async def _receive_action_with_resync(
        self,
        *,
        websocket: WebSocket,
        session: Session,
        expected_step_id: int,
        expected_length: int | None,
        result: LifecycleResult,
    ) -> ActionMessage | object | None:
        while True:
            try:
                msg = await websocket.receive_json()
            except WebSocketDisconnect:
                raise

            kind = msg.get("type")
            if kind == "failure":
                # Client gave up on this step. Record and end the episode.
                try:
                    failure = FailureMessage(
                        category=FailureCategory(
                            msg.get("data", {}).get("category", "policy_exception")
                        ),
                        summary=msg.get("data", {}).get("summary", "client failure"),
                        step_id=msg.get("data", {}).get("step_id", expected_step_id),
                    )
                except ValueError:
                    failure = FailureMessage(
                        category=FailureCategory.POLICY_EXCEPTION,
                        summary="client failure",
                        step_id=expected_step_id,
                    )
                result.failures.append(failure)
                return _CLIENT_FAILURE_SENTINEL

            if kind != "action":
                if not await self._record_invalid(websocket, session, "expected action"):
                    return None
                continue

            raw_data = msg.get("data", {})
            raw_invalid_reason = validate_raw_action_payload(raw_data)
            if raw_invalid_reason is not None:
                await websocket.send_json(
                    {
                        "type": "action_rejected",
                        "step_id": raw_data.get("step_id") if isinstance(raw_data, dict) else None,
                        "reason": raw_invalid_reason,
                    }
                )
                result.failures.append(
                    FailureMessage(
                        category=FailureCategory.INVALID_ACTION,
                        summary=raw_invalid_reason,
                        step_id=raw_data.get("step_id") if isinstance(raw_data, dict) else None,
                    )
                )
                count = self._manager.record_invalid_message(session)
                if count >= self._manager.config.max_invalid_messages:
                    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                    return None
                continue

            try:
                action = action_message_adapter.validate_python(raw_data)
            except Exception as exc:
                if not await self._record_invalid(
                    websocket,
                    session,
                    f"malformed action payload: {exc}",
                    category="invalid_action",
                ):
                    return None
                continue

            invalid_reason = validate_action_payload(
                action,
                expected_step_id=expected_step_id,
                expected_length=expected_length,
                joint_bounds=self._joint_bounds,
            )
            if invalid_reason is not None:
                await websocket.send_json(
                    {
                        "type": "action_rejected",
                        "step_id": action.step_id,
                        "reason": invalid_reason,
                    }
                )
                result.failures.append(
                    FailureMessage(
                        category=FailureCategory.INVALID_ACTION,
                        summary=invalid_reason,
                        step_id=action.step_id,
                    )
                )
                count = self._manager.record_invalid_message(session)
                if count >= self._manager.config.max_invalid_messages:
                    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                    return None
                continue

            if not action.valid:
                # Client self-reported an invalid action. Record but accept the
                # message; the episode ends as a technical failure on the next
                # iteration. Mirrors fake server behavior.
                result.failures.append(
                    FailureMessage(
                        category=FailureCategory.INVALID_ACTION,
                        summary=action.invalid_reason or "client-marked invalid",
                        step_id=action.step_id,
                    )
                )
                result.actions_received.append(action)
                return _CLIENT_FAILURE_SENTINEL

            result.actions_received.append(action)
            return action

    async def _record_invalid(
        self,
        websocket: WebSocket,
        session: Session,
        summary: str,
        *,
        category: str = "compatibility",
    ) -> bool:
        await websocket.send_json(
            {"type": "error", "category": category, "summary": summary}
        )
        count = self._manager.record_invalid_message(session)
        if count >= self._manager.config.max_invalid_messages:
            await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
            return False
        return True


# Sentinel so callers can distinguish "client failed" from a successful
# action without the type system getting in the way.
_CLIENT_FAILURE_SENTINEL = object()

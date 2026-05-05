from __future__ import annotations

from fastapi import WebSocket

from asimovbm_client.runner import RunnerConfig, StepSynchronousRunner
from asimovbm_client.transport import TransportConfig, WebSocketBenchmarkServer
from asimovbm_protocol import (
    PROTOCOL_VERSION,
    PackageSubmission,
    TerminalMessage,
    TerminalStatus,
    to_payload,
)
from asimovbm_protocol.adapters import action_message_adapter
from asimovbm_server.sessions import Session
from asimovbm_server.simulation import (
    G1SlamBatchAdapter,
    G1SlamBatchConfig,
    G1SlamStepOutcome,
    G1SlamStepper,
    G1SlamStepperConfig,
)

from .conftest import BOOTSTRAP_TOKEN


def _transport(base_url: str) -> WebSocketBenchmarkServer:
    return WebSocketBenchmarkServer(
        TransportConfig(
            server_url=base_url,
            bootstrap_token=BOOTSTRAP_TOKEN,
            receive_timeout_s=2.0,
        )
    )


async def _ack_bootstrap(websocket: WebSocket) -> None:
    first = await websocket.receive_json()
    assert first["type"] == "bootstrap"
    await websocket.send_json(
        {"type": "bootstrap_ack", "data": {"protocol_version": PROTOCOL_VERSION}}
    )


class G1BatchTerminalOrchestrator:
    def __init__(self) -> None:
        self.result = None
        self.report = None

    async def run(self, session: Session, websocket: WebSocket) -> None:
        await _ack_bootstrap(websocket)
        self.result = G1SlamBatchAdapter(G1SlamBatchConfig(steps=8)).run()
        self.report = self.result.to_report_context()
        report_ref = websocket.app.state.session_manager.make_report_ref()
        websocket.app.state.reports[report_ref] = self.report
        websocket.app.state.session_manager.finalize(session, report_ref=report_ref)
        await websocket.send_json(
            {
                "type": "terminal",
                "data": to_payload(
                    TerminalMessage(TerminalStatus.REPORT_READY, report_ref=report_ref)
                ),
            }
        )


class G1PolicyInLoopOrchestrator:
    def __init__(self) -> None:
        self.stepper = G1SlamStepper.from_config(
            G1SlamStepperConfig(max_steps=1, lidar_rays=9)
        )
        self.outcome: G1SlamStepOutcome | None = None
        self.report = None

    async def run(self, session: Session, websocket: WebSocket) -> None:
        await _ack_bootstrap(websocket)
        step = self.stepper.next_step()
        await websocket.send_json({"type": "step", "data": to_payload(step)})
        msg = await websocket.receive_json()
        assert msg["type"] == "action"
        action = action_message_adapter.validate_python(msg["data"])
        self.outcome = self.stepper.apply_action(action)
        self.report = self.stepper.smoke_result().to_report_context()
        report_ref = websocket.app.state.session_manager.make_report_ref()
        websocket.app.state.reports[report_ref] = self.report
        websocket.app.state.session_manager.finalize(session, report_ref=report_ref)
        await websocket.send_json(
            {
                "type": "terminal",
                "data": to_payload(
                    TerminalMessage(TerminalStatus.REPORT_READY, report_ref=report_ref)
                ),
            }
        )


def test_server_run_can_terminal_after_g1_slam_batch_smoke(
    server_factory,
    sample_package: PackageSubmission,
) -> None:
    orchestrator = G1BatchTerminalOrchestrator()
    _, _, base_url, _ = server_factory(orchestrator=orchestrator)
    transport = _transport(base_url)

    try:
        result = StepSynchronousRunner(
            transport,
            sample_package,
            lambda step: step,
            lambda _step: [0.0, 0.0],
            RunnerConfig("<server-issued>", action_size=2),
        ).run()
    finally:
        transport.close()

    assert result.ok
    assert result.steps_completed == 0
    assert result.terminal is not None
    assert result.terminal.report_ref is not None
    assert orchestrator.report["maturity"] == "g1_slam_batch_smoke"
    assert orchestrator.report["trajectory_summary"]["points"] > 1


def test_server_run_can_apply_client_action_to_g1_slam_stepper(
    server_factory,
    sample_package: PackageSubmission,
) -> None:
    orchestrator = G1PolicyInLoopOrchestrator()
    _, _, base_url, _ = server_factory(orchestrator=orchestrator)
    transport = _transport(base_url)

    def policy(step):
        plan = next(sensor for sensor in step.sensors if sensor.name == "navigation_plan")
        command = plan.data["recommended_command"]
        return [command["linear"], command["yaw_rate"]]

    try:
        result = StepSynchronousRunner(
            transport,
            sample_package,
            lambda step: step,
            policy,
            RunnerConfig("<server-issued>", action_size=2),
        ).run()
    finally:
        transport.close()

    assert result.ok
    assert result.steps_completed == 1
    assert orchestrator.outcome is not None
    assert orchestrator.outcome.step_id == 1
    assert orchestrator.outcome.sim_time == orchestrator.stepper.config.dt
    assert orchestrator.report["maturity"] == "g1_slam_policy_in_loop_smoke"
    assert orchestrator.report["telemetry"]["actions"][0]["step_id"] == 1

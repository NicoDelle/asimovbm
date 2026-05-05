from __future__ import annotations

from fastapi import WebSocket

from asimovbm_client.runner import RunnerConfig, StepSynchronousRunner
from asimovbm_client.transport import TransportConfig, WebSocketBenchmarkServer
from asimovbm_protocol import PROTOCOL_VERSION, FailureCategory, PackageSubmission
from asimovbm_server.sessions import Session

from .conftest import BOOTSTRAP_TOKEN


def _transport(base_url: str, *, receive_timeout_s: float) -> WebSocketBenchmarkServer:
    return WebSocketBenchmarkServer(
        TransportConfig(
            server_url=base_url,
            bootstrap_token=BOOTSTRAP_TOKEN,
            receive_timeout_s=receive_timeout_s,
        )
    )


def test_real_transport_retries_one_transient_control_timeout(
    server_factory,
    sample_package: PackageSubmission,
    echo_policy,
) -> None:
    _, _, base_url, _ = server_factory(delay_before_step_id={1: 0.8})
    transformer, policy = echo_policy
    transport = _transport(base_url, receive_timeout_s=0.5)

    try:
        result = StepSynchronousRunner(
            transport,
            sample_package,
            transformer,
            policy,
            RunnerConfig("<server-issued>", action_size=2, retry_timeouts=1),
        ).run()
    finally:
        transport.close()

    assert result.ok
    assert result.steps_completed == 2
    assert any(item.category == FailureCategory.TIMEOUT for item in result.telemetry)
    assert not result.failures


class DisconnectAfterBootstrap:
    async def run(self, session: Session, websocket: WebSocket) -> None:
        first = await websocket.receive_json()
        assert first["type"] == "bootstrap"
        await websocket.send_json(
            {
                "type": "bootstrap_ack",
                "data": {"protocol_version": PROTOCOL_VERSION},
            }
        )
        await websocket.close()


def test_disconnect_during_control_loop_is_technical_failure(
    server_factory,
    sample_package: PackageSubmission,
    echo_policy,
) -> None:
    _, _, base_url, _ = server_factory(orchestrator=DisconnectAfterBootstrap())
    transformer, policy = echo_policy
    transport = _transport(base_url, receive_timeout_s=1.0)

    try:
        result = StepSynchronousRunner(
            transport,
            sample_package,
            transformer,
            policy,
            RunnerConfig("<server-issued>", action_size=2),
        ).run()
    finally:
        transport.close()

    assert result.terminal is None
    assert result.failures[0].category == FailureCategory.DISCONNECT
    assert result.steps_completed == 0

from __future__ import annotations

import time

import pytest

from asimovbm_client.runner import RunnerConfig, StepSynchronousRunner
from asimovbm_client.transport import TransportConfig, WebSocketBenchmarkServer
from asimovbm_protocol import (
    ActionMessage,
    FailureCategory,
    PackageSubmission,
    ProtocolError,
    SessionBootstrap,
)

from .conftest import BOOTSTRAP_TOKEN


def _wait_for(predicate, *, timeout_s: float = 2.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition did not become true before timeout")


def _transport(base_url: str, *, receive_timeout_s: float = 1.0) -> WebSocketBenchmarkServer:
    return WebSocketBenchmarkServer(
        TransportConfig(
            server_url=base_url,
            bootstrap_token=BOOTSTRAP_TOKEN,
            receive_timeout_s=receive_timeout_s,
        )
    )


def test_real_transport_completes_server_issued_step_loop(
    server_factory,
    sample_package: PackageSubmission,
    echo_policy,
) -> None:
    _, _, base_url, orchestrator = server_factory()
    transformer, policy = echo_policy
    transport = _transport(base_url)

    try:
        result = StepSynchronousRunner(
            transport,
            sample_package,
            transformer,
            policy,
            RunnerConfig("<server-issued>", action_size=2, participant_id="p1"),
        ).run()
    finally:
        transport.close()

    assert result.ok
    assert result.steps_completed == 2
    assert result.actions_sent == 2
    assert result.terminal is not None
    assert result.terminal.report_ref is not None
    assert orchestrator.last_result is not None
    assert [action.step_id for action in orchestrator.last_result.actions_received] == [1, 2]


def test_policy_exception_is_sent_as_failure_without_action(
    server_factory,
    sample_package: PackageSubmission,
) -> None:
    _, _, base_url, orchestrator = server_factory()
    transport = _transport(base_url)

    def policy(_observation):
        raise RuntimeError("policy token=secret failed")

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

    assert result.failures[0].category == FailureCategory.POLICY_EXCEPTION
    assert not result.actions_sent
    _wait_for(
        lambda: orchestrator.last_result is not None
        and bool(orchestrator.last_result.failures)
    )
    assert orchestrator.last_result is not None
    assert orchestrator.last_result.failures[0].category == FailureCategory.POLICY_EXCEPTION
    assert not orchestrator.last_result.actions_received


def test_stale_step_action_is_rejected_before_next_simulation_step(
    server_factory,
    sample_package: PackageSubmission,
) -> None:
    _, _, base_url, orchestrator = server_factory()
    transport = _transport(base_url)

    try:
        transport.connect(SessionBootstrap("<server-issued>"))
        assert transport.submit_package(sample_package).accepted
        step = transport.next_step()
        transport.submit_action(
            ActionMessage(step.step_id + 10, [0.0, 0.0], latency_ms=0.1)
        )

        with pytest.raises(ProtocolError, match="step_id"):
            transport.next_step()
    finally:
        transport.close()

    assert orchestrator.last_result is not None
    assert orchestrator.last_result.failures[-1].category == FailureCategory.INVALID_ACTION
    assert not orchestrator.last_result.actions_received


def test_string_action_values_are_rejected_before_pydantic_coercion(
    server_factory,
    sample_package: PackageSubmission,
) -> None:
    _, _, base_url, orchestrator = server_factory()
    transport = _transport(base_url)

    try:
        transport.connect(SessionBootstrap("<server-issued>"))
        assert transport.submit_package(sample_package).accepted
        step = transport.next_step()
        transport.submit_action(
            ActionMessage(step.step_id, ["0.0", 0.0], latency_ms=0.1)  # type: ignore[list-item]
        )

        with pytest.raises(ProtocolError, match="JSON number"):
            transport.next_step()
    finally:
        transport.close()

    assert orchestrator.last_result is not None
    assert orchestrator.last_result.failures[-1].category == FailureCategory.INVALID_ACTION
    assert not orchestrator.last_result.actions_received

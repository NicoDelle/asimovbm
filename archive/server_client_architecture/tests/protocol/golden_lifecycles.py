"""Checked-in golden lifecycle fixtures.

These fixtures capture the canonical message orderings the server transport
and client runner must reproduce. Server-side and client-side tests load them
to keep the lifecycle stable across implementations.

Lifecycles covered:

- ``successful_run``: connect → submit_package(accepted) → step → action →
  terminal(report_ready)
- ``validation_rejected``: connect → submit_package(rejected) → no control loop
- ``transformer_exception``: connect → submit_package(accepted) → step →
  failure(transformer_exception) → terminal(failed)
- ``policy_exception``: connect → submit_package(accepted) → step →
  failure(policy_exception) → terminal(failed)
- ``invalid_action``: connect → submit_package(accepted) → step →
  action(invalid) → terminal(invalid)
- ``timeout_retry``: connect → submit_package(accepted) → failure(timeout,
  retry_count=1) → step → action → terminal(report_ready)
- ``terminal_report_ref``: terminal payload carries an opaque ``report_ref``
"""

from __future__ import annotations

from typing import Any

from asimovbm_protocol import (
    ActionMessage,
    ClientCapabilities,
    FailureCategory,
    FailureMessage,
    PackageSubmission,
    SensorReading,
    SessionBootstrap,
    StepMessage,
    TaskEvent,
    TerminalMessage,
    TerminalStatus,
    ValidationResponse,
    ValidationStatus,
    to_payload,
)


def _bootstrap() -> SessionBootstrap:
    return SessionBootstrap(
        run_token="golden-run-1",
        participant_id="golden-participant",
        capabilities=ClientCapabilities(),
    )


def _package() -> PackageSubmission:
    return PackageSubmission(
        name="goldenbot",
        model={"format": "mjcf", "path": "robot.xml"},
        sensors=[
            {"name": "lidar", "kind": "lidar"},
            {"name": "pose", "kind": "proprioception"},
        ],
        action_mapping={"mode": "joint_target", "joints": ["x", "y"]},
        robot_metadata={"morphology": "wheeled"},
    )


def _step(step_id: int = 1) -> StepMessage:
    return StepMessage(
        step_id=step_id,
        sim_time=step_id * 0.025,
        control_dt=0.025,
        sensors=[
            SensorReading(
                name="pose",
                kind="proprioception",
                data={"x": 0.0, "y": 0.0, "yaw": 0.0},
            ),
            SensorReading(
                name="lidar",
                kind="lidar",
                data=[1.0, 1.0, 1.0],
            ),
        ],
        task_events=[TaskEvent("come_here", payload={"target": "human-1"})],
    )


def _action(step_id: int = 1, *, invalid: bool = False) -> ActionMessage:
    if invalid:
        return ActionMessage(
            step_id=step_id,
            action=[],
            latency_ms=2.0,
            invalid_reason="wrong shape",
        )
    return ActionMessage(step_id=step_id, action=[0.1, 0.0], latency_ms=2.0)


def _terminal(
    status: TerminalStatus = TerminalStatus.COMPLETED,
    *,
    failures: list[FailureMessage] | None = None,
    report_ref: str | None = "srv://reports/golden-run-1",
) -> TerminalMessage:
    return TerminalMessage(
        status=status,
        report_ref=report_ref,
        failures=list(failures or []),
    )


SUCCESSFUL_RUN: tuple[Any, ...] = (
    _bootstrap(),
    _package(),
    ValidationResponse(ValidationStatus.ACCEPTED, settings={"control_dt": 0.025}),
    _step(1),
    _action(1),
    _terminal(TerminalStatus.REPORT_READY),
)

VALIDATION_REJECTED: tuple[Any, ...] = (
    _bootstrap(),
    _package(),
    ValidationResponse(
        ValidationStatus.REJECTED,
        errors=["sensor.lidar.range_max missing"],
    ),
)

TRANSFORMER_EXCEPTION: tuple[Any, ...] = (
    _bootstrap(),
    _package(),
    ValidationResponse(ValidationStatus.ACCEPTED),
    _step(1),
    FailureMessage(
        category=FailureCategory.TRANSFORMER_EXCEPTION,
        summary="ValueError in transformer",
        step_id=1,
    ),
    _terminal(TerminalStatus.FAILED, failures=[
        FailureMessage(
            category=FailureCategory.TRANSFORMER_EXCEPTION,
            summary="ValueError in transformer",
            step_id=1,
        )
    ]),
)

POLICY_EXCEPTION: tuple[Any, ...] = (
    _bootstrap(),
    _package(),
    ValidationResponse(ValidationStatus.ACCEPTED),
    _step(1),
    FailureMessage(
        category=FailureCategory.POLICY_EXCEPTION,
        summary="RuntimeError in policy",
        step_id=1,
    ),
    _terminal(TerminalStatus.FAILED, failures=[
        FailureMessage(
            category=FailureCategory.POLICY_EXCEPTION,
            summary="RuntimeError in policy",
            step_id=1,
        )
    ]),
)

INVALID_ACTION: tuple[Any, ...] = (
    _bootstrap(),
    _package(),
    ValidationResponse(ValidationStatus.ACCEPTED),
    _step(1),
    _action(1, invalid=True),
    _terminal(TerminalStatus.INVALID, failures=[
        FailureMessage(
            category=FailureCategory.INVALID_ACTION,
            summary="wrong shape",
            step_id=1,
        )
    ]),
)

TIMEOUT_RETRY: tuple[Any, ...] = (
    _bootstrap(),
    _package(),
    ValidationResponse(ValidationStatus.ACCEPTED),
    FailureMessage(
        category=FailureCategory.TIMEOUT,
        summary="Transient timeout on next_step",
        retry_count=1,
    ),
    _step(1),
    _action(1),
    _terminal(TerminalStatus.REPORT_READY),
)

TERMINAL_REPORT_REF: tuple[Any, ...] = (
    _terminal(
        TerminalStatus.REPORT_READY,
        report_ref="srv://reports/opaque-9c1b6d",
    ),
)


GOLDEN_LIFECYCLES: dict[str, tuple[Any, ...]] = {
    "successful_run": SUCCESSFUL_RUN,
    "validation_rejected": VALIDATION_REJECTED,
    "transformer_exception": TRANSFORMER_EXCEPTION,
    "policy_exception": POLICY_EXCEPTION,
    "invalid_action": INVALID_ACTION,
    "timeout_retry": TIMEOUT_RETRY,
    "terminal_report_ref": TERMINAL_REPORT_REF,
}


def lifecycle_payloads(name: str) -> list[dict[str, Any]]:
    """Return the lifecycle as JSON-compatible payloads.

    Useful for golden-fixture comparison in transport tests where the wire
    representation matters more than the dataclass identity.
    """
    return [to_payload(message) for message in GOLDEN_LIFECYCLES[name]]


__all__ = [
    "GOLDEN_LIFECYCLES",
    "INVALID_ACTION",
    "POLICY_EXCEPTION",
    "SUCCESSFUL_RUN",
    "TERMINAL_REPORT_REF",
    "TIMEOUT_RETRY",
    "TRANSFORMER_EXCEPTION",
    "VALIDATION_REJECTED",
    "lifecycle_payloads",
]

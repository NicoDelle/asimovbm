"""Compatibility tests for the shared protocol models.

The shared package ``asimovbm_protocol`` owns the message dataclasses; the
client re-exports them from ``asimovbm_client.protocol`` for backwards
compatibility. Both import paths must resolve to the same class objects so
isinstance/equality checks across server and client code stay sound.
"""

from __future__ import annotations

import json

import asimovbm_protocol as protocol
import asimovbm_client.protocol as client_protocol
from asimovbm_protocol import (
    PROTOCOL_VERSION,
    ActionMessage,
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


PUBLIC_NAMES = [
    "ActionMessage",
    "ClientCapabilities",
    "FailureCategory",
    "FailureMessage",
    "PROTOCOL_VERSION",
    "PackageSubmission",
    "ProtocolError",
    "SensorReading",
    "SessionBootstrap",
    "StepMessage",
    "TaskEvent",
    "TerminalMessage",
    "TerminalStatus",
    "ValidationResponse",
    "ValidationStatus",
]


def test_protocol_version_is_v0() -> None:
    assert PROTOCOL_VERSION == "asimovbm.client.v0"


def test_client_protocol_reexports_share_identity_with_shared_protocol() -> None:
    """Server and client must observe the same class objects, not copies."""
    for name in PUBLIC_NAMES:
        shared = getattr(protocol, name)
        client_side = getattr(client_protocol, name)
        assert shared is client_side, (
            f"{name} must be the same object in both packages "
            f"(shared={shared!r}, client={client_side!r})"
        )


def test_session_bootstrap_payload_round_trip() -> None:
    bootstrap = SessionBootstrap(run_token="r-1", participant_id="alice")
    payload = to_payload(bootstrap)
    assert payload["run_token"] == "r-1"
    assert payload["protocol_version"] == PROTOCOL_VERSION
    assert payload["capabilities"]["policy_runtime"] == "python"


def test_step_message_payload_includes_sensors() -> None:
    step = StepMessage(
        step_id=1,
        sim_time=0.0,
        control_dt=0.025,
        sensors=[SensorReading("lidar", "lidar", [1.0, 2.0])],
        task_events=[TaskEvent("come_here", payload={"target": "human-1"})],
    )
    payload = to_payload(step)
    assert payload["step_id"] == 1
    assert payload["sensors"][0]["name"] == "lidar"
    assert payload["task_events"][0]["name"] == "come_here"


def test_action_message_validity_helper() -> None:
    valid = ActionMessage(step_id=1, action=[0.0, 0.1], latency_ms=1.0)
    invalid = ActionMessage(
        step_id=1, action=[], latency_ms=1.0, invalid_reason="wrong shape"
    )
    assert valid.valid
    assert not invalid.valid


def test_validation_response_accepted_helper() -> None:
    accepted = ValidationResponse(ValidationStatus.ACCEPTED)
    rejected = ValidationResponse(ValidationStatus.REJECTED, errors=["bad"])
    assert accepted.accepted
    assert not rejected.accepted


def test_failure_message_records_step_and_category() -> None:
    failure = FailureMessage(
        category=FailureCategory.INVALID_ACTION,
        summary="wrong shape",
        step_id=7,
        details={"action": [0.0]},
    )
    payload = to_payload(failure)
    assert payload["category"] == "invalid_action"
    assert payload["step_id"] == 7


def test_terminal_message_carries_report_ref_only() -> None:
    terminal = TerminalMessage(
        status=TerminalStatus.COMPLETED, report_ref="srv://reports/abc"
    )
    payload = to_payload(terminal)
    assert payload["status"] == "completed"
    assert payload["report_ref"] == "srv://reports/abc"
    assert "report" not in payload  # Full report is server-side only.


def test_to_payload_is_json_serializable() -> None:
    package = PackageSubmission(
        name="testbot",
        model={"format": "mjcf", "path": "robot.xml"},
        sensors=[{"name": "lidar", "kind": "lidar"}],
        action_mapping={"mode": "joint_target", "joints": ["x"]},
    )
    payload = to_payload(package)
    json.dumps(payload)

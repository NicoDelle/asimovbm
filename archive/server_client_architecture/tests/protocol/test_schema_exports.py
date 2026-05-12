"""Schema export coverage and adapter validation tests."""

from __future__ import annotations

import json

import pytest

from asimovbm_protocol import (
    PROTOCOL_VERSION,
    FailureCategory,
    TerminalStatus,
    ValidationStatus,
    to_payload,
)
from asimovbm_protocol.adapters import (
    action_message_adapter,
    package_submission_adapter,
    session_bootstrap_adapter,
    step_message_adapter,
)
from asimovbm_protocol.schema import (
    PUBLIC_ENUMS,
    PUBLIC_MESSAGE_NAMES,
    export_protocol_schema,
    message_schema,
)
from .golden_lifecycles import (
    GOLDEN_LIFECYCLES,
    SUCCESSFUL_RUN,
    lifecycle_payloads,
)


# --- Schema export -------------------------------------------------------


def test_schema_lists_every_public_message() -> None:
    schema = export_protocol_schema()
    assert schema["protocol_version"] == PROTOCOL_VERSION
    assert set(schema["messages"].keys()) == set(PUBLIC_MESSAGE_NAMES)


def test_schema_lists_every_public_enum() -> None:
    schema = export_protocol_schema()
    expected = {enum.__name__: [member.value for member in enum] for enum in PUBLIC_ENUMS}
    assert schema["enums"] == expected
    assert "ACCEPTED" not in schema["enums"]["ValidationStatus"]  # values, not names
    assert "accepted" in schema["enums"]["ValidationStatus"]


def test_message_schema_unknown_name_raises() -> None:
    with pytest.raises(KeyError):
        message_schema("NotAMessage")


def test_step_message_schema_includes_sensors_field() -> None:
    schema = message_schema("StepMessage")
    properties = schema.get("properties", {})
    assert "sensors" in properties
    assert "step_id" in properties


def test_export_protocol_schema_is_json_serializable() -> None:
    json.dumps(export_protocol_schema())


# --- Adapter round-trips -------------------------------------------------


def test_session_bootstrap_adapter_round_trip() -> None:
    payload = {"run_token": "r-1", "participant_id": "p"}
    bootstrap = session_bootstrap_adapter.validate_python(payload)
    assert bootstrap.run_token == "r-1"
    assert bootstrap.protocol_version == PROTOCOL_VERSION
    dumped = session_bootstrap_adapter.dump_python(bootstrap)
    assert dumped["run_token"] == "r-1"


def test_package_submission_adapter_validates_required_fields() -> None:
    with pytest.raises(Exception):
        package_submission_adapter.validate_python({"name": "missing-fields"})


def test_step_message_adapter_validates_action_message_pairing() -> None:
    step = step_message_adapter.validate_python(
        {
            "step_id": 7,
            "sim_time": 0.1,
            "control_dt": 0.025,
            "sensors": [{"name": "lidar", "kind": "lidar", "data": [1.0]}],
        }
    )
    assert step.step_id == 7
    action = action_message_adapter.validate_python(
        {"step_id": 7, "action": [0.1, 0.2], "latency_ms": 1.5}
    )
    assert action.step_id == 7
    assert action.valid


def test_action_message_adapter_rejects_non_finite_handled_at_validation_layer() -> None:
    """Adapter accepts any float; finite/range checks are server policy.

    This test fixes that decision: the protocol layer parses floats; the
    server-side action validator (Unit 4) enforces NaN/Inf/range rules.
    """
    action = action_message_adapter.validate_python(
        {"step_id": 1, "action": [0.0], "latency_ms": 1.0}
    )
    assert action.action == [0.0]


# --- Golden lifecycle replay --------------------------------------------


def test_every_golden_lifecycle_serializes_and_round_trips() -> None:
    for name in GOLDEN_LIFECYCLES:
        payloads = lifecycle_payloads(name)
        for payload in payloads:
            json.dumps(payload)


def test_successful_run_lifecycle_terminal_carries_report_ref() -> None:
    *_, terminal = SUCCESSFUL_RUN
    payload = to_payload(terminal)
    assert payload["report_ref"] is not None
    assert payload["status"] in {
        TerminalStatus.COMPLETED.value,
        TerminalStatus.REPORT_READY.value,
    }


def test_invalid_action_lifecycle_records_invalid_action_failure() -> None:
    *_, terminal = GOLDEN_LIFECYCLES["invalid_action"]
    failure_categories = {f.category for f in terminal.failures}
    assert FailureCategory.INVALID_ACTION in failure_categories


def test_timeout_retry_lifecycle_records_retry_count() -> None:
    lifecycle = GOLDEN_LIFECYCLES["timeout_retry"]
    timeout_failures = [m for m in lifecycle if hasattr(m, "category") and getattr(m, "category", None) == FailureCategory.TIMEOUT]
    assert any(f.retry_count == 1 for f in timeout_failures)


def test_validation_status_strenum_value() -> None:
    assert ValidationStatus.ACCEPTED.value == "accepted"

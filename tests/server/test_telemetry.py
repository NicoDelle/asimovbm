from __future__ import annotations

import pytest

from asimovbm_protocol import ActionMessage, SensorReading, StepMessage
from asimovbm_server.runner import (
    TelemetryValidationError,
    copy_smoke_result,
    validate_step_telemetry,
)
from asimovbm_server.simulation import FakeSmokeSimulation


def test_validate_step_telemetry_requires_pose_sensor() -> None:
    step = StepMessage(
        step_id=1,
        sim_time=0.0,
        control_dt=0.025,
        sensors=[],
    )

    with pytest.raises(TelemetryValidationError, match="pose"):
        validate_step_telemetry(step)


def test_validate_step_telemetry_rejects_missing_pose_value() -> None:
    step = StepMessage(
        step_id=1,
        sim_time=0.0,
        control_dt=0.025,
        sensors=[SensorReading("pose", "proprioception", {"x": 0.0, "y": 0.0})],
    )

    with pytest.raises(TelemetryValidationError, match="pose.yaw"):
        validate_step_telemetry(step)


def test_copy_smoke_result_is_independent_from_adapter_mutation() -> None:
    sim = FakeSmokeSimulation()
    step = sim.next_step()
    sim.apply_action(ActionMessage(step.step_id, [0.0], 1.0))

    copied = copy_smoke_result(sim.smoke_result())
    copied.telemetry["actions"].append({"step_id": 99})

    fresh = sim.smoke_result()
    assert len(fresh.telemetry["actions"]) == 1

from __future__ import annotations

import pytest

from asimovbm_protocol import SensorReading, StepMessage, TaskEvent
from examples.policies.g1_slam_policy import G1SlamPolicy, G1SlamTransformer


def _step(*, sensors=None, events=None) -> StepMessage:
    return StepMessage(
        step_id=1,
        sim_time=0.0,
        control_dt=0.05,
        sensors=sensors
        if sensors is not None
        else [SensorReading("pose", "proprioception", {"x": 0.0, "y": 0.0, "yaw": 0.0})],
        task_events=events
        if events is not None
        else [TaskEvent("come_here", {"goal": {"x": 1.0, "y": 0.0}})],
    )


def test_g1_slam_example_policy_returns_declared_action_vector() -> None:
    observation = G1SlamTransformer()(_step())
    action = G1SlamPolicy()(observation)

    assert len(action) == 2
    assert action[0] > 0
    assert action[1] == pytest.approx(0.0)


def test_g1_slam_example_transformer_requires_protocol_sensors() -> None:
    with pytest.raises(ValueError, match="missing required sensor: pose"):
        G1SlamTransformer()(_step(sensors=[]))


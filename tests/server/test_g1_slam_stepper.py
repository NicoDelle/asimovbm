from __future__ import annotations

import pytest

from asimovbm_protocol import ActionMessage
from asimovbm_server.simulation import (
    G1SlamStepper,
    G1SlamStepperConfig,
    SimulationStepError,
)


def _stepper(max_steps: int = 3) -> G1SlamStepper:
    return G1SlamStepper.from_config(
        G1SlamStepperConfig(max_steps=max_steps, lidar_rays=9)
    )


def test_stepper_emits_benchmark_compatible_observation() -> None:
    stepper = _stepper()

    step = stepper.next_step()

    assert step.step_id == 1
    assert step.sim_time == 0.0
    assert step.control_dt == stepper.config.dt
    assert [sensor.name for sensor in step.sensors] == [
        "pose",
        "lidar",
        "navigation_plan",
    ]
    assert step.sensors[0].data["goal_distance"] > 0
    assert step.sensors[1].data["num_rays"] == 9
    assert step.task_events[0].name == "come_here"


def test_stepper_applies_client_action_and_advances_simulated_time() -> None:
    stepper = _stepper()
    step = stepper.next_step()

    outcome = stepper.apply_action(ActionMessage(step.step_id, [0.2, 0.1], 3.0))

    assert outcome.step_id == 1
    assert outcome.action == [0.2, 0.1]
    assert outcome.sim_time == stepper.config.dt
    assert stepper.step_count == 1
    assert stepper.trajectory[-1].x != stepper.trajectory[0].x
    smoke = stepper.smoke_result()
    assert smoke.maturity == "g1_slam_policy_in_loop_smoke"
    assert smoke.steps == 1
    assert smoke.telemetry["actions"][0]["step_id"] == 1


def test_stepper_requires_matching_action_for_pending_step() -> None:
    stepper = _stepper()
    step = stepper.next_step()

    with pytest.raises(SimulationStepError, match="does not match"):
        stepper.apply_action(ActionMessage(step.step_id + 1, [0.0, 0.0], 1.0))

    with pytest.raises(SimulationStepError, match="still needs an action"):
        stepper.next_step()


def test_stepper_becomes_terminal_at_max_steps() -> None:
    stepper = _stepper(max_steps=1)
    step = stepper.next_step()
    stepper.apply_action(ActionMessage(step.step_id, [0.0, 0.0], 1.0))

    assert stepper.terminal
    with pytest.raises(SimulationStepError, match="terminal"):
        stepper.next_step()

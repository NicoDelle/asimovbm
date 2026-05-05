"""G1-style client policy example for the benchmark protocol.

This module intentionally lives under ``examples/policies``: it is participant
side code. It consumes only protocol ``StepMessage`` observations and returns
actions through the normal client runner path. The benchmark server remains the
owner of simulation state.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, hypot, sin
from typing import Any

from asimovbm_protocol import StepMessage


@dataclass(frozen=True)
class G1NavigationObservation:
    step_id: int
    sim_time: float
    control_dt: float
    x: float
    y: float
    yaw: float
    goal_x: float
    goal_y: float


class G1SlamTransformer:
    """Adapt protocol sensor streams into a navigation observation."""

    def __call__(self, step: StepMessage) -> G1NavigationObservation:
        pose = _sensor_data(step, "pose")
        goal = _goal_from_events(step)
        return G1NavigationObservation(
            step_id=step.step_id,
            sim_time=step.sim_time,
            control_dt=step.control_dt,
            x=float(pose["x"]),
            y=float(pose["y"]),
            yaw=float(pose.get("yaw", 0.0)),
            goal_x=float(goal["x"]),
            goal_y=float(goal["y"]),
        )


class G1SlamPolicy:
    """Tiny proportional navigation policy returning ``[linear, yaw_rate]``."""

    def __init__(
        self,
        *,
        max_linear: float = 0.6,
        max_yaw_rate: float = 1.2,
        goal_tolerance: float = 0.05,
    ) -> None:
        self.max_linear = max_linear
        self.max_yaw_rate = max_yaw_rate
        self.goal_tolerance = goal_tolerance

    def __call__(self, observation: G1NavigationObservation) -> list[float]:
        dx = observation.goal_x - observation.x
        dy = observation.goal_y - observation.y
        distance = hypot(dx, dy)
        if distance <= self.goal_tolerance:
            return [0.0, 0.0]

        desired_yaw = atan2(dy, dx)
        yaw_error = _wrap_angle(desired_yaw - observation.yaw)
        linear = min(self.max_linear, distance) * max(0.0, cos(yaw_error))
        yaw_rate = max(-self.max_yaw_rate, min(self.max_yaw_rate, 2.0 * yaw_error))
        return [linear, yaw_rate]


def _sensor_data(step: StepMessage, name: str) -> dict[str, Any]:
    for sensor in step.sensors:
        if sensor.name == name:
            if not isinstance(sensor.data, dict):
                raise ValueError(f"sensor {name!r} must carry object data")
            return sensor.data
    raise ValueError(f"missing required sensor: {name}")


def _goal_from_events(step: StepMessage) -> dict[str, Any]:
    for event in step.task_events:
        if event.name == "come_here":
            goal = event.payload.get("goal")
            if isinstance(goal, dict):
                return goal
    raise ValueError("missing required come_here goal event")


def _wrap_angle(value: float) -> float:
    return atan2(sin(value), cos(value))


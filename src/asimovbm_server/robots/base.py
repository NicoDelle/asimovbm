"""Robot embodiment adapter contracts for local validation."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from asimovbm_protocol import ActionMessage
from asimovbm_server.episodes import Pose2D


@dataclass(frozen=True)
class RobotProfile:
    id: str
    embodiment_kind: str
    action_mode: str = "mobile_base_velocity"
    model_path: Path | None = None
    body_radius: float = 0.25
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RobotState:
    step_id: int
    time_s: float
    pose: Pose2D
    velocity: tuple[float, float, float]
    contacts: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class RobotAdapter(Protocol):
    profile: RobotProfile

    def reset(self, pose: Pose2D) -> None:
        ...

    def state(self) -> RobotState:
        ...

    def apply_action(self, action: ActionMessage, dt: float) -> RobotState:
        ...

    def viewer_target(self) -> tuple[Any, Any] | None:
        ...


class FakeMobileBaseRobot:
    """Deterministic mobile-base adapter used by dry-runs and unit tests."""

    def __init__(self, profile: RobotProfile | None = None) -> None:
        self.profile = profile or RobotProfile(
            id="fake-mobile-base",
            embodiment_kind="mobile_base",
        )
        self._pose = Pose2D(0.0, 0.0, 0.0)
        self._step_id = 0
        self._time_s = 0.0
        self._velocity = (0.0, 0.0, 0.0)
        self.actions: list[ActionMessage] = []

    def reset(self, pose: Pose2D) -> None:
        self._pose = pose
        self._step_id = 0
        self._time_s = 0.0
        self._velocity = (0.0, 0.0, 0.0)
        self.actions.clear()

    def state(self) -> RobotState:
        return RobotState(
            step_id=self._step_id,
            time_s=self._time_s,
            pose=self._pose,
            velocity=self._velocity,
        )

    def apply_action(self, action: ActionMessage, dt: float) -> RobotState:
        if not action.valid:
            raise ValueError(action.invalid_reason or "invalid action")
        if len(action.action) != 2:
            raise ValueError("mobile-base validation actions require [linear_velocity, yaw_rate]")
        linear_velocity = float(action.action[0])
        yaw_rate = float(action.action[1])
        yaw = _wrap_angle(self._pose.yaw + yaw_rate * dt)
        self._pose = Pose2D(
            x=self._pose.x + linear_velocity * math.cos(yaw) * dt,
            y=self._pose.y + linear_velocity * math.sin(yaw) * dt,
            yaw=yaw,
        )
        self._velocity = (linear_velocity, 0.0, yaw_rate)
        self._step_id += 1
        self._time_s += dt
        self.actions.append(action)
        return self.state()

    def viewer_target(self) -> tuple[Any, Any] | None:
        return None


def _wrap_angle(value: float) -> float:
    return math.atan2(math.sin(value), math.cos(value))

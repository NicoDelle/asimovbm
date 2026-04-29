from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .controller import PurePursuitConfig
from .geometry import Pose2D


@dataclass(frozen=True)
class LocomotionConfig:
    mode: str
    policy_path: Path | None
    observation_size: int | None
    action_scale: float
    kp: float
    kd: float


@dataclass(frozen=True)
class NavigationConfig:
    start: Pose2D
    goal: tuple[float, float]
    steps: int
    controller: PurePursuitConfig
    locomotion: LocomotionConfig


DEFAULT_NAVIGATION_CONFIG = NavigationConfig(
    start=Pose2D(-4.2, -3.2, 0.0),
    goal=(-4.2, -1.0),
    steps=900,
    controller=PurePursuitConfig(),
    locomotion=LocomotionConfig(
        mode="kinematic",
        policy_path=Path("policies/g1/policy.onnx"),
        observation_size=None,
        action_scale=0.25,
        kp=35.0,
        kd=1.0,
    ),
)


def load_navigation_config(path: str | Path) -> NavigationConfig:
    config_path = Path(path)
    if not config_path.exists():
        return DEFAULT_NAVIGATION_CONFIG

    with config_path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)

    return NavigationConfig(
        start=_read_start(payload.get("start", {})),
        goal=_read_goal(payload.get("goal", {})),
        steps=int(payload.get("steps", DEFAULT_NAVIGATION_CONFIG.steps)),
        controller=_read_controller(payload.get("controller", {})),
        locomotion=_read_locomotion(payload.get("locomotion", {})),
    )


def _read_start(payload: dict[str, Any]) -> Pose2D:
    return Pose2D(
        x=float(payload.get("x", DEFAULT_NAVIGATION_CONFIG.start.x)),
        y=float(payload.get("y", DEFAULT_NAVIGATION_CONFIG.start.y)),
        yaw=float(payload.get("yaw", DEFAULT_NAVIGATION_CONFIG.start.yaw)),
    )


def _read_goal(payload: dict[str, Any]) -> tuple[float, float]:
    return (
        float(payload.get("x", DEFAULT_NAVIGATION_CONFIG.goal[0])),
        float(payload.get("y", DEFAULT_NAVIGATION_CONFIG.goal[1])),
    )


def _read_locomotion(payload: dict[str, Any]) -> LocomotionConfig:
    raw_policy_path = payload.get("policy_path", DEFAULT_NAVIGATION_CONFIG.locomotion.policy_path)
    raw_observation_size = payload.get("observation_size", DEFAULT_NAVIGATION_CONFIG.locomotion.observation_size)
    return LocomotionConfig(
        mode=str(payload.get("mode", DEFAULT_NAVIGATION_CONFIG.locomotion.mode)),
        policy_path=Path(raw_policy_path) if raw_policy_path else None,
        observation_size=int(raw_observation_size) if raw_observation_size is not None else None,
        action_scale=float(payload.get("action_scale", DEFAULT_NAVIGATION_CONFIG.locomotion.action_scale)),
        kp=float(payload.get("kp", DEFAULT_NAVIGATION_CONFIG.locomotion.kp)),
        kd=float(payload.get("kd", DEFAULT_NAVIGATION_CONFIG.locomotion.kd)),
    )


def _read_controller(payload: dict[str, Any]) -> PurePursuitConfig:
    defaults = DEFAULT_NAVIGATION_CONFIG.controller
    return PurePursuitConfig(
        lookahead=float(payload.get("lookahead", defaults.lookahead)),
        waypoint_tolerance=float(payload.get("waypoint_tolerance", defaults.waypoint_tolerance)),
        goal_tolerance=float(payload.get("goal_tolerance", defaults.goal_tolerance)),
        max_linear_speed=float(payload.get("max_linear_speed", defaults.max_linear_speed)),
        max_yaw_rate=float(payload.get("max_yaw_rate", defaults.max_yaw_rate)),
    )

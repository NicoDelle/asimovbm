from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .controller import PurePursuitConfig
from .geometry import Pose2D
from .world import RectObstacle, World2D, default_world


@dataclass(frozen=True)
class LocomotionConfig:
    mode: str
    policy_path: Path | None
    observation_size: int | None
    observation_profile: str
    action_scale: float
    kp: float
    kd: float


@dataclass(frozen=True)
class DynamicObstaclesConfig:
    mode: str
    blue_cylinders: bool
    blue_cylinder_seed: int
    blue_cylinder_count: int | None
    npc_policy: str


@dataclass(frozen=True)
class VisualizationConfig:
    camera_lookat: tuple[float, float, float] | None
    camera_distance: float | None
    camera_azimuth: float | None
    camera_elevation: float | None
    fixed_camera: bool
    show_trajectory: bool
    trajectory_interval_steps: int


@dataclass(frozen=True)
class NavigationConfig:
    start: Pose2D
    goal: tuple[float, float]
    steps: int
    controller: PurePursuitConfig
    locomotion: LocomotionConfig
    world: World2D | None
    dynamic_obstacles: DynamicObstaclesConfig
    visualization: VisualizationConfig


DEFAULT_NAVIGATION_CONFIG = NavigationConfig(
    start=Pose2D(-4.2, -3.2, 0.0),
    goal=(-4.2, -1.0),
    steps=900,
    controller=PurePursuitConfig(),
    locomotion=LocomotionConfig(
        mode="kinematic",
        policy_path=Path("policies/g1/policy.onnx"),
        observation_size=None,
        observation_profile="generic",
        action_scale=0.25,
        kp=35.0,
        kd=1.0,
    ),
    world=None,
    dynamic_obstacles=DynamicObstaclesConfig(
        mode="none",
        blue_cylinders=False,
        blue_cylinder_seed=7,
        blue_cylinder_count=None,
        npc_policy="social_patrol",
    ),
    visualization=VisualizationConfig(
        camera_lookat=None,
        camera_distance=None,
        camera_azimuth=None,
        camera_elevation=None,
        fixed_camera=False,
        show_trajectory=False,
        trajectory_interval_steps=25,
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
        world=_read_world(payload.get("world")),
        dynamic_obstacles=_read_dynamic_obstacles(payload.get("dynamic_obstacles", {})),
        visualization=_read_visualization(payload.get("visualization", {})),
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
        observation_profile=str(
            payload.get(
                "observation_profile",
                DEFAULT_NAVIGATION_CONFIG.locomotion.observation_profile,
            )
        ),
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


def _read_world(payload: dict[str, Any] | None) -> World2D | None:
    if payload is None:
        return DEFAULT_NAVIGATION_CONFIG.world

    defaults = default_world()
    return World2D(
        x_min=float(payload.get("x_min", defaults.x_min)),
        y_min=float(payload.get("y_min", defaults.y_min)),
        x_max=float(payload.get("x_max", defaults.x_max)),
        y_max=float(payload.get("y_max", defaults.y_max)),
        obstacles=tuple(_read_obstacle(obstacle) for obstacle in payload.get("obstacles", ())),
    )


def _read_obstacle(payload: dict[str, Any]) -> RectObstacle:
    return RectObstacle(
        x_min=float(payload["x_min"]),
        y_min=float(payload["y_min"]),
        x_max=float(payload["x_max"]),
        y_max=float(payload["y_max"]),
    )


def _read_dynamic_obstacles(payload: dict[str, Any]) -> DynamicObstaclesConfig:
    defaults = DEFAULT_NAVIGATION_CONFIG.dynamic_obstacles
    raw_mode = payload.get("mode")
    if raw_mode is None:
        raw_mode = "blue_cylinders" if payload.get("blue_cylinders", defaults.blue_cylinders) else defaults.mode
    mode = _normalize_dynamic_obstacle_mode(str(raw_mode))
    count = _read_optional_int(
        payload,
        "count",
        _read_optional_int(payload, "blue_cylinder_count", defaults.blue_cylinder_count),
    )
    return DynamicObstaclesConfig(
        mode=mode,
        blue_cylinders=mode == "blue_cylinders",
        blue_cylinder_seed=int(
            payload.get("seed", payload.get("blue_cylinder_seed", defaults.blue_cylinder_seed))
        ),
        blue_cylinder_count=count,
        npc_policy=str(payload.get("npc_policy", defaults.npc_policy)),
    )


def _read_visualization(payload: dict[str, Any]) -> VisualizationConfig:
    defaults = DEFAULT_NAVIGATION_CONFIG.visualization
    camera = payload.get("camera", {})
    return VisualizationConfig(
        camera_lookat=_read_camera_lookat(camera.get("lookat")),
        camera_distance=_read_optional_float(camera, "distance", defaults.camera_distance),
        camera_azimuth=_read_optional_float(camera, "azimuth", defaults.camera_azimuth),
        camera_elevation=_read_optional_float(camera, "elevation", defaults.camera_elevation),
        fixed_camera=bool(camera.get("fixed", defaults.fixed_camera)),
        show_trajectory=bool(payload.get("show_trajectory", defaults.show_trajectory)),
        trajectory_interval_steps=int(
            payload.get("trajectory_interval_steps", defaults.trajectory_interval_steps)
        ),
    )


def _read_camera_lookat(payload: dict[str, Any] | None) -> tuple[float, float, float] | None:
    if payload is None:
        return DEFAULT_NAVIGATION_CONFIG.visualization.camera_lookat
    return (
        float(payload.get("x", 0.0)),
        float(payload.get("y", 0.0)),
        float(payload.get("z", 1.0)),
    )


def _read_optional_float(
    payload: dict[str, Any],
    key: str,
    default: float | None,
) -> float | None:
    value = payload.get(key, default)
    return float(value) if value is not None else None


def _read_optional_int(
    payload: dict[str, Any],
    key: str,
    default: int | None,
) -> int | None:
    value = payload.get(key, default)
    return int(value) if value is not None else None


def _normalize_dynamic_obstacle_mode(mode: str) -> str:
    normalized = mode.replace("-", "_")
    if normalized in {"", "off", "false", "none"}:
        return "none"
    if normalized in {"blue", "cylinders", "blue_cylinder", "blue_cylinders"}:
        return "blue_cylinders"
    if normalized in {"npc", "npcs", "people", "persons", "pedestrians"}:
        return "npcs"
    raise ValueError(
        f"Unsupported dynamic_obstacles.mode: {mode}. "
        "Use 'none', 'blue_cylinders', or 'npcs'."
    )

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from .geometry import Pose2D
from .world import RectObstacle, World2D

DYNAMIC_SCENARIO_START = Pose2D(-6.0, 0.0, 0.0)
DYNAMIC_SCENARIO_GOAL = (10.0, 0.0)
DYNAMIC_SCENARIO_STEPS = 1800

DynamicObstacleMode = str


@dataclass(frozen=True)
class DynamicObstacle:
    name: str
    center: tuple[float, float]
    axis: tuple[float, float]
    radius: float
    half_height: float
    amplitude_m: float
    period_s: float
    phase_rad: float
    mode: DynamicObstacleMode = "blue_cylinder"
    policy: str = "sinusoidal_patrol"

    def xy_at(self, sim_time: float) -> tuple[float, float]:
        offset = self.amplitude_m * math.sin(
            (2.0 * math.pi * sim_time / self.period_s) + self.phase_rad
        )
        return (
            self.center[0] + self.axis[0] * offset,
            self.center[1] + self.axis[1] * offset,
        )

    def velocity_at(self, sim_time: float) -> tuple[float, float]:
        angular_speed = 2.0 * math.pi / self.period_s
        speed = self.amplitude_m * angular_speed * math.cos(
            (angular_speed * sim_time) + self.phase_rad
        )
        return (self.axis[0] * speed, self.axis[1] * speed)

    def yaw_at(self, sim_time: float) -> float:
        phase = (2.0 * math.pi * sim_time / self.period_s) + self.phase_rad
        direction = 1.0 if math.cos(phase) >= 0.0 else -1.0
        return math.atan2(self.axis[1] * direction, self.axis[0] * direction)

    def rect_at(self, sim_time: float) -> RectObstacle:
        x, y = self.xy_at(sim_time)
        return RectObstacle(
            x_min=x - self.radius,
            y_min=y - self.radius,
            x_max=x + self.radius,
            y_max=y + self.radius,
        )


DynamicCylinder = DynamicObstacle


def make_default_dynamic_obstacles(
    mode: str,
    *,
    seed: int = 7,
    count: int | None = None,
    world: World2D | None = None,
    npc_policy: str = "social_patrol",
    obstacles: tuple[object, ...] = (),
) -> tuple[DynamicObstacle, ...]:
    normalized_mode = _normalize_mode(mode)
    if normalized_mode == "none":
        return ()
    if obstacles:
        return _configured_obstacles(normalized_mode, obstacles, npc_policy)
    target_count = 3 if count is None else max(0, count)
    if target_count == 0:
        return ()
    world = world or make_dynamic_cylinder_world()
    rng = random.Random(seed)
    selected = _select_clear_patrols(
        _default_patrol_specs(normalized_mode, rng, npc_policy),
        world=world,
        target_count=target_count,
    )
    if len(selected) < target_count:
        selected.extend(
            _sample_clear_patrols(
                normalized_mode,
                rng,
                world=world,
                start_index=len(selected),
                target_count=target_count - len(selected),
                npc_policy=npc_policy,
            )
        )
    return tuple(
        _with_name(spec, _name_for_mode(normalized_mode, index))
        for index, spec in enumerate(selected[:target_count])
    )


def _configured_obstacles(
    mode: str,
    obstacles: tuple[object, ...],
    npc_policy: str,
) -> tuple[DynamicObstacle, ...]:
    radius = 0.28 if mode == "npcs" else 0.22
    half_height = 0.85 if mode == "npcs" else 0.35
    visual_mode = "npc" if mode == "npcs" else "blue_cylinder"
    policy = npc_policy if mode == "npcs" else "sinusoidal_patrol"
    return tuple(
        DynamicObstacle(
            name=getattr(obstacle, "name", None) or _name_for_mode(mode, index),
            center=getattr(obstacle, "center"),
            axis=_unit_vector(getattr(obstacle, "axis")),
            radius=getattr(obstacle, "radius", None) or radius,
            half_height=getattr(obstacle, "half_height", None) or half_height,
            amplitude_m=getattr(obstacle, "amplitude_m"),
            period_s=getattr(obstacle, "period_s"),
            phase_rad=getattr(obstacle, "phase_rad"),
            mode=visual_mode,
            policy=getattr(obstacle, "policy", None) or policy,
        )
        for index, obstacle in enumerate(obstacles)
    )


def make_default_dynamic_cylinders(
    seed: int = 7,
    *,
    count: int | None = None,
    world: World2D | None = None,
) -> tuple[DynamicObstacle, ...]:
    return make_default_dynamic_obstacles(
        "blue_cylinders",
        seed=seed,
        count=count,
        world=world,
    )


def make_default_npcs(
    seed: int = 7,
    *,
    count: int | None = None,
    world: World2D | None = None,
    policy: str = "social_patrol",
) -> tuple[DynamicObstacle, ...]:
    return make_default_dynamic_obstacles(
        "npcs",
        seed=seed,
        count=count,
        world=world,
        npc_policy=policy,
    )


def _default_patrol_specs(
    mode: str,
    rng: random.Random,
    npc_policy: str,
) -> list[DynamicObstacle]:
    radius = 0.28 if mode == "npcs" else 0.22
    half_height = 0.85 if mode == "npcs" else 0.35
    visual_mode = "npc" if mode == "npcs" else "blue_cylinder"
    policy = npc_policy if mode == "npcs" else "sinusoidal_patrol"
    period_bias = 1.6 if mode == "npcs" else 1.0
    return [
        DynamicObstacle(
            name="",
            center=(-3.0, -1.25),
            axis=_unit_vector((0.0, 1.0)),
            radius=radius,
            half_height=half_height,
            amplitude_m=1.05,
            period_s=11.0 * period_bias,
            phase_rad=rng.uniform(0.0, 2.0 * math.pi),
            mode=visual_mode,
            policy=policy,
        ),
        DynamicObstacle(
            name="",
            center=(0.15, 1.25),
            axis=_unit_vector((0.0, 1.0)),
            radius=radius,
            half_height=half_height,
            amplitude_m=1.0,
            period_s=12.5 * period_bias,
            phase_rad=rng.uniform(0.0, 2.0 * math.pi),
            mode=visual_mode,
            policy=policy,
        ),
        DynamicObstacle(
            name="",
            center=(3.2, -1.15),
            axis=_unit_vector((0.0, 1.0)),
            radius=radius,
            half_height=half_height,
            amplitude_m=1.05,
            period_s=13.5 * period_bias,
            phase_rad=rng.uniform(0.0, 2.0 * math.pi),
            mode=visual_mode,
            policy=policy,
        ),
        DynamicObstacle(
            name="",
            center=(-1.9, 2.35),
            axis=_unit_vector((1.0, 0.0)),
            radius=radius,
            half_height=half_height,
            amplitude_m=0.9,
            period_s=10.5 * period_bias,
            phase_rad=rng.uniform(0.0, 2.0 * math.pi),
            mode=visual_mode,
            policy=policy,
        ),
        DynamicObstacle(
            name="",
            center=(1.9, -2.3),
            axis=_unit_vector((1.0, 0.0)),
            radius=radius,
            half_height=half_height,
            amplitude_m=0.9,
            period_s=14.0 * period_bias,
            phase_rad=rng.uniform(0.0, 2.0 * math.pi),
            mode=visual_mode,
            policy=policy,
        ),
    ]


def _select_clear_patrols(
    candidates: list[DynamicObstacle],
    *,
    world: World2D,
    target_count: int,
) -> list[DynamicObstacle]:
    selected: list[DynamicObstacle] = []
    for candidate in candidates:
        if _patrol_is_clear(candidate, world):
            selected.append(candidate)
        if len(selected) >= target_count:
            break
    return selected


def _sample_clear_patrols(
    mode: str,
    rng: random.Random,
    *,
    world: World2D,
    start_index: int,
    target_count: int,
    npc_policy: str,
) -> list[DynamicObstacle]:
    radius = 0.28 if mode == "npcs" else 0.22
    half_height = 0.85 if mode == "npcs" else 0.35
    visual_mode = "npc" if mode == "npcs" else "blue_cylinder"
    policy = npc_policy if mode == "npcs" else "sinusoidal_patrol"
    selected: list[DynamicObstacle] = []
    attempts = 0
    while len(selected) < target_count and attempts < 300:
        attempts += 1
        axis = _unit_vector((1.0, 0.0)) if attempts % 2 == 0 else _unit_vector((0.0, 1.0))
        amplitude = rng.uniform(0.55, 1.05)
        clearance = radius + amplitude + 0.35
        x = rng.uniform(world.x_min + clearance, world.x_max - clearance)
        y = rng.uniform(world.y_min + clearance, world.y_max - clearance)
        candidate = DynamicObstacle(
            name="",
            center=(x, y),
            axis=axis,
            radius=radius,
            half_height=half_height,
            amplitude_m=amplitude,
            period_s=rng.uniform(10.0, 16.0) * (1.6 if mode == "npcs" else 1.0),
            phase_rad=rng.uniform(0.0, 2.0 * math.pi),
            mode=visual_mode,
            policy=policy,
        )
        if _patrol_is_clear(candidate, world):
            selected.append(candidate)
    if len(selected) < target_count:
        raise ValueError(
            f"Could not place {target_count + start_index} dynamic {mode} without "
            "overlapping static obstacles. Reduce the count or enlarge the world."
        )
    return selected


def _patrol_is_clear(obstacle: DynamicObstacle, world: World2D) -> bool:
    sample_count = 64
    margin = obstacle.radius + 0.10
    for index in range(sample_count):
        sim_time = obstacle.period_s * index / sample_count
        x, y = obstacle.xy_at(sim_time)
        if world.is_occupied(x, y, margin=margin):
            return False
    return True


def _with_name(obstacle: DynamicObstacle, name: str) -> DynamicObstacle:
    return DynamicObstacle(
        name=name,
        center=obstacle.center,
        axis=obstacle.axis,
        radius=obstacle.radius,
        half_height=obstacle.half_height,
        amplitude_m=obstacle.amplitude_m,
        period_s=obstacle.period_s,
        phase_rad=obstacle.phase_rad,
        mode=obstacle.mode,
        policy=obstacle.policy,
    )


def _name_for_mode(mode: str, index: int) -> str:
    if mode == "npcs":
        return f"person_npc_{index}"
    return f"blue_cylinder_{index}"


def _normalize_mode(mode: str) -> str:
    normalized = mode.replace("-", "_")
    if normalized in {"", "off", "false", "none"}:
        return "none"
    if normalized in {"blue", "cylinders", "blue_cylinder", "blue_cylinders"}:
        return "blue_cylinders"
    if normalized in {"npc", "npcs", "people", "persons", "pedestrians"}:
        return "npcs"
    raise ValueError(
        f"Unsupported dynamic obstacle mode: {mode}. "
        "Use 'none', 'blue_cylinders', or 'npcs'."
    )


def make_dynamic_cylinder_world() -> World2D:
    return World2D(
        x_min=-12.0,
        y_min=-7.0,
        x_max=14.0,
        y_max=7.0,
        obstacles=(),
    )


def _unit_vector(vector: tuple[float, float]) -> tuple[float, float]:
    length = math.hypot(vector[0], vector[1])
    if length == 0:
        raise ValueError("Cannot normalize a zero-length vector")
    return (vector[0] / length, vector[1] / length)

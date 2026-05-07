from __future__ import annotations

import math
import random
from dataclasses import dataclass

from .geometry import Pose2D
from .world import RectObstacle, World2D

DYNAMIC_SCENARIO_START = Pose2D(-6.0, 0.0, 0.0)
DYNAMIC_SCENARIO_GOAL = (10.0, 0.0)
DYNAMIC_SCENARIO_STEPS = 1800


@dataclass(frozen=True)
class DynamicCylinder:
    name: str
    center: tuple[float, float]
    axis: tuple[float, float]
    radius: float
    half_height: float
    amplitude_m: float
    period_s: float
    phase_rad: float

    def xy_at(self, sim_time: float) -> tuple[float, float]:
        offset = self.amplitude_m * math.sin(
            (2.0 * math.pi * sim_time / self.period_s) + self.phase_rad
        )
        return (
            self.center[0] + self.axis[0] * offset,
            self.center[1] + self.axis[1] * offset,
        )

    def rect_at(self, sim_time: float) -> RectObstacle:
        x, y = self.xy_at(sim_time)
        return RectObstacle(
            x_min=x - self.radius,
            y_min=y - self.radius,
            x_max=x + self.radius,
            y_max=y + self.radius,
        )


def make_default_dynamic_cylinders(seed: int = 7) -> tuple[DynamicCylinder, ...]:
    rng = random.Random(seed)
    return (
        DynamicCylinder(
            name="blue_cylinder_0",
            center=(-3.2, -1.2),
            axis=_unit_vector((1.0, 0.20)),
            radius=0.22,
            half_height=0.35,
            amplitude_m=1.5,
            period_s=12.0,
            phase_rad=rng.uniform(0.0, 2.0 * math.pi),
        ),
        DynamicCylinder(
            name="blue_cylinder_1",
            center=(-1.0, 1.4),
            axis=_unit_vector((-0.35, 1.0)),
            radius=0.25,
            half_height=0.35,
            amplitude_m=1.2,
            period_s=10.0,
            phase_rad=rng.uniform(0.0, 2.0 * math.pi),
        ),
        DynamicCylinder(
            name="blue_cylinder_2",
            center=(1.4, -1.3),
            axis=_unit_vector((0.8, -0.55)),
            radius=0.20,
            half_height=0.35,
            amplitude_m=1.4,
            period_s=14.0,
            phase_rad=rng.uniform(0.0, 2.0 * math.pi),
        ),
        DynamicCylinder(
            name="blue_cylinder_3",
            center=(3.2, 1.1),
            axis=_unit_vector((0.15, 1.0)),
            radius=0.24,
            half_height=0.35,
            amplitude_m=1.3,
            period_s=13.0,
            phase_rad=rng.uniform(0.0, 2.0 * math.pi),
        ),
        DynamicCylinder(
            name="blue_cylinder_4",
            center=(5.0, -1.4),
            axis=_unit_vector((1.0, -0.10)),
            radius=0.22,
            half_height=0.35,
            amplitude_m=1.5,
            period_s=15.0,
            phase_rad=rng.uniform(0.0, 2.0 * math.pi),
        ),
        DynamicCylinder(
            name="blue_cylinder_5",
            center=(6.8, 1.3),
            axis=_unit_vector((-0.45, 1.0)),
            radius=0.25,
            half_height=0.35,
            amplitude_m=1.1,
            period_s=11.0,
            phase_rad=rng.uniform(0.0, 2.0 * math.pi),
        ),
        DynamicCylinder(
            name="blue_cylinder_6",
            center=(8.3, -0.8),
            axis=_unit_vector((0.55, 1.0)),
            radius=0.20,
            half_height=0.35,
            amplitude_m=1.0,
            period_s=9.5,
            phase_rad=rng.uniform(0.0, 2.0 * math.pi),
        ),
        DynamicCylinder(
            name="blue_cylinder_7",
            center=(0.4, 0.2),
            axis=_unit_vector((0.0, 1.0)),
            radius=0.18,
            half_height=0.35,
            amplitude_m=1.0,
            period_s=8.5,
            phase_rad=rng.uniform(0.0, 2.0 * math.pi),
        ),
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

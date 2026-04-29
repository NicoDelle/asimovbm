from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, hypot, pi, sin


@dataclass(frozen=True)
class Pose2D:
    x: float
    y: float
    yaw: float = 0.0

    def moved(self, linear_velocity: float, yaw_rate: float, dt: float) -> "Pose2D":
        next_yaw = wrap_angle(self.yaw + yaw_rate * dt)
        return Pose2D(
            self.x + linear_velocity * cos(next_yaw) * dt,
            self.y + linear_velocity * sin(next_yaw) * dt,
            next_yaw,
        )


def wrap_angle(angle: float) -> float:
    while angle > pi:
        angle -= 2.0 * pi
    while angle < -pi:
        angle += 2.0 * pi
    return angle


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def distance_xy(a: tuple[float, float], b: tuple[float, float]) -> float:
    return hypot(a[0] - b[0], a[1] - b[1])


def heading_to(source: tuple[float, float], target: tuple[float, float]) -> float:
    return atan2(target[1] - source[1], target[0] - source[0])


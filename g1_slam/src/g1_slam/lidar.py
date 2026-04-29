from __future__ import annotations

from dataclasses import dataclass
from math import cos, pi, sin

from .geometry import Pose2D, wrap_angle
from .world import World2D


@dataclass(frozen=True)
class LaserScan:
    angles: tuple[float, ...]
    ranges: tuple[float, ...]
    max_range: float

    def global_points(self, pose: Pose2D) -> list[tuple[float, float]]:
        points: list[tuple[float, float]] = []
        for angle, distance in zip(self.angles, self.ranges, strict=True):
            yaw = pose.yaw + angle
            points.append((pose.x + distance * cos(yaw), pose.y + distance * sin(yaw)))
        return points


def simulate_lidar(
    world: World2D,
    pose: Pose2D,
    *,
    num_rays: int = 181,
    fov: float = 2.0 * pi,
    max_range: float = 5.5,
    step: float = 0.04,
) -> LaserScan:
    if num_rays < 2:
        raise ValueError("num_rays must be at least 2")
    start = -0.5 * fov
    delta = fov / (num_rays - 1)
    angles: list[float] = []
    ranges: list[float] = []

    for i in range(num_rays):
        local_angle = wrap_angle(start + i * delta)
        yaw = pose.yaw + local_angle
        hit_range = max_range
        distance = 0.0
        while distance <= max_range:
            x = pose.x + distance * cos(yaw)
            y = pose.y + distance * sin(yaw)
            if world.is_occupied(x, y):
                hit_range = distance
                break
            distance += step
        angles.append(local_angle)
        ranges.append(min(hit_range, max_range))

    return LaserScan(tuple(angles), tuple(ranges), max_range)


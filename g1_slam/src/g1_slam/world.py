from __future__ import annotations

from dataclasses import dataclass

from .geometry import Pose2D


@dataclass(frozen=True)
class RectObstacle:
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    def contains(self, x: float, y: float, margin: float = 0.0) -> bool:
        return (
            self.x_min - margin <= x <= self.x_max + margin
            and self.y_min - margin <= y <= self.y_max + margin
        )


@dataclass(frozen=True)
class World2D:
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    obstacles: tuple[RectObstacle, ...]

    def contains(self, x: float, y: float, margin: float = 0.0) -> bool:
        return (
            self.x_min + margin <= x <= self.x_max - margin
            and self.y_min + margin <= y <= self.y_max - margin
        )

    def is_occupied(self, x: float, y: float, margin: float = 0.0) -> bool:
        if not self.contains(x, y, margin=margin):
            return True
        return any(obstacle.contains(x, y, margin=margin) for obstacle in self.obstacles)

    def collides(self, pose: Pose2D, radius: float) -> bool:
        return self.is_occupied(pose.x, pose.y, margin=radius)


def default_world() -> World2D:
    return World2D(
        x_min=-5.0,
        y_min=-4.0,
        x_max=7.0,
        y_max=4.0,
        obstacles=(
            RectObstacle(-1.5, -3.0, -1.1, 1.2),
            RectObstacle(0.6, -0.4, 1.1, 3.2),
            RectObstacle(2.2, -3.2, 2.8, -0.7),
            RectObstacle(3.8, 0.6, 4.3, 3.7),
            RectObstacle(4.7, -2.8, 5.2, -0.4),
        ),
    )


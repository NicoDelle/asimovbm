from __future__ import annotations

from dataclasses import dataclass

from .geometry import Pose2D, clamp, distance_xy, heading_to, wrap_angle


@dataclass(frozen=True)
class VelocityCommand:
    linear: float
    yaw_rate: float


@dataclass(frozen=True)
class PurePursuitConfig:
    lookahead: float = 0.55
    waypoint_tolerance: float = 0.25
    goal_tolerance: float = 0.28
    max_linear_speed: float = 0.65
    max_yaw_rate: float = 1.4


class PurePursuitController:
    def __init__(self, config: PurePursuitConfig | None = None) -> None:
        self.config = config or PurePursuitConfig()
        self.waypoint_index = 0

    def reset(self) -> None:
        self.waypoint_index = 0

    def command(self, pose: Pose2D, path: list[tuple[float, float]], goal: tuple[float, float]) -> VelocityCommand:
        if not path or distance_xy((pose.x, pose.y), goal) <= self.config.goal_tolerance:
            return VelocityCommand(0.0, 0.0)

        self.waypoint_index = min(self.waypoint_index, max(0, len(path) - 1))
        while self.waypoint_index < len(path) - 1:
            if distance_xy((pose.x, pose.y), path[self.waypoint_index]) > self.config.lookahead:
                break
            self.waypoint_index += 1

        target = path[self.waypoint_index]
        heading_error = wrap_angle(heading_to((pose.x, pose.y), target) - pose.yaw)
        yaw_rate = clamp(2.0 * heading_error, -self.config.max_yaw_rate, self.config.max_yaw_rate)
        speed_scale = max(0.15, 1.0 - abs(heading_error) / 1.7)
        linear = self.config.max_linear_speed * speed_scale
        return VelocityCommand(linear, yaw_rate)


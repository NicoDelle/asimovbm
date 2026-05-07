"""Obstacle-aware local policy for visual validation episodes."""

from __future__ import annotations

import math

from asimovbm_protocol import ActionMessage
from asimovbm_server.episodes import EpisodeObservation, PublicEntityObservation


class ObstacleAwareNavigationPolicy:
    id = "obstacle-aware-nav"

    def __init__(self) -> None:
        self._episode_id: str | None = None
        self._waypoint_index = 0
        self._path: list[tuple[float, float]] = []

    def act(self, observation: EpisodeObservation) -> ActionMessage:
        if observation.episode_id != self._episode_id or observation.step_id == 0:
            self._episode_id = observation.episode_id
            self._waypoint_index = 0
            self._path = []

        target = _goal_target(observation)
        if target is None:
            return ActionMessage(observation.step_id, [0.0, 0.0], latency_ms=0.0)

        pose = observation.robot_pose
        if not self._path:
            self._path = _detour_path(observation, target)
        path = self._path
        if path:
            self._waypoint_index = min(self._waypoint_index, len(path) - 1)
            while self._waypoint_index < len(path) - 1:
                current = path[self._waypoint_index]
                if math.hypot(current[0] - pose.x, current[1] - pose.y) > 0.30:
                    break
                self._waypoint_index += 1
            target = path[self._waypoint_index]

        heading_error = _wrap_angle(math.atan2(target[1] - pose.y, target[0] - pose.x) - pose.yaw)
        yaw_rate = max(-2.2, min(2.2, 3.2 * heading_error))
        distance = math.hypot(target[0] - pose.x, target[1] - pose.y)
        linear_velocity = min(0.9, max(0.10, distance))
        if abs(heading_error) > 1.0:
            linear_velocity = 0.08
        return ActionMessage(observation.step_id, [linear_velocity, yaw_rate], latency_ms=0.0)


def _goal_target(observation: EpisodeObservation) -> tuple[float, float] | None:
    goal = observation.public_goal
    if goal is None:
        return None
    if goal.x is not None and goal.y is not None:
        return goal.x, goal.y
    if goal.target_human_id:
        target = next(
            (
                entity
                for entity in observation.visible_entities
                if entity.id == goal.target_human_id
            ),
            None,
        )
        if target is not None:
            return target.x, target.y
    return None


def _detour_path(
    observation: EpisodeObservation,
    target: tuple[float, float],
) -> list[tuple[float, float]]:
    pose = observation.robot_pose
    blockers: list[PublicEntityObservation] = []
    for entity in observation.visible_entities:
        if entity.kind not in {"obstacle", "human"}:
            continue
        distance_to_segment = _point_segment_distance(
            entity.x,
            entity.y,
            pose.x,
            pose.y,
            target[0],
            target[1],
        )
        clearance = entity.radius + 0.45
        ahead = _dot(entity.x - pose.x, entity.y - pose.y, target[0] - pose.x, target[1] - pose.y) > 0
        if ahead and distance_to_segment < clearance:
            blockers.append(entity)
    if not blockers:
        return [target]

    min_x = min(entity.x - entity.radius for entity in blockers)
    max_x = max(entity.x + entity.radius for entity in blockers)
    top_lane = max(entity.y + entity.radius for entity in blockers) + 0.75
    bottom_lane = min(entity.y - entity.radius for entity in blockers) - 0.75
    top_lane, bottom_lane = _clamp_lanes(observation, top_lane, bottom_lane)
    lane_y = bottom_lane if abs(bottom_lane - pose.y) <= abs(top_lane - pose.y) else top_lane
    return [
        (min_x - 0.70, lane_y),
        (max_x + 0.85, lane_y),
        target,
    ]


def _clamp_lanes(
    observation: EpisodeObservation,
    top_lane: float,
    bottom_lane: float,
) -> tuple[float, float]:
    bounds = observation.metadata.get("world_bounds")
    if not isinstance(bounds, (list, tuple)) or len(bounds) != 4:
        return top_lane, bottom_lane
    _x_min, y_min, _x_max, y_max = (float(value) for value in bounds)
    margin = 0.35
    return min(top_lane, y_max - margin), max(bottom_lane, y_min + margin)


def _point_segment_distance(
    px: float,
    py: float,
    ax: float,
    ay: float,
    bx: float,
    by: float,
) -> float:
    ab_x = bx - ax
    ab_y = by - ay
    length_sq = ab_x * ab_x + ab_y * ab_y
    if length_sq == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, _dot(px - ax, py - ay, ab_x, ab_y) / length_sq))
    closest_x = ax + t * ab_x
    closest_y = ay + t * ab_y
    return math.hypot(px - closest_x, py - closest_y)


def _dot(ax: float, ay: float, bx: float, by: float) -> float:
    return ax * bx + ay * by


def _wrap_angle(value: float) -> float:
    return math.atan2(math.sin(value), math.cos(value))

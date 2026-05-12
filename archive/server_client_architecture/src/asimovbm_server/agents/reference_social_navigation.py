"""Deterministic reference policy for validation dry-runs."""

from __future__ import annotations

import math

from asimovbm_protocol import ActionMessage
from asimovbm_server.episodes import EpisodeObservation


class ReferenceSocialNavigationPolicy:
    id = "reference-social-nav"

    def act(self, observation: EpisodeObservation) -> ActionMessage:
        goal = observation.public_goal
        if goal is None:
            return ActionMessage(observation.step_id, [0.0, 0.0], latency_ms=0.0)
        if goal.x is not None and goal.y is not None:
            target_x, target_y = goal.x, goal.y
        elif goal.target_human_id:
            target = next(
                (
                    entity
                    for entity in observation.visible_entities
                    if entity.id == goal.target_human_id
                ),
                None,
            )
            if target is None:
                return ActionMessage(observation.step_id, [0.0, 0.0], latency_ms=0.0)
            target_x, target_y = target.x, target.y
        else:
            return ActionMessage(observation.step_id, [0.0, 0.0], latency_ms=0.0)

        pose = observation.robot_pose
        heading_error = _wrap_angle(math.atan2(target_y - pose.y, target_x - pose.x) - pose.yaw)
        yaw_rate = max(-1.0, min(1.0, 3.0 * heading_error))
        linear_velocity = 0.5 if abs(heading_error) < 0.7 else 0.1
        return ActionMessage(
            observation.step_id,
            [linear_velocity, yaw_rate],
            latency_ms=0.0,
        )


def _wrap_angle(value: float) -> float:
    return math.atan2(math.sin(value), math.cos(value))

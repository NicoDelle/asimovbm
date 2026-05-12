"""Social-cue-aware local validation policy."""

from __future__ import annotations

import math

from asimovbm_protocol import ActionMessage
from asimovbm_server.episodes import EpisodeObservation


class SocialCueNavigationPolicy:
    id = "social-cue-nav"

    def act(self, observation: EpisodeObservation) -> ActionMessage:
        target = _target_after_public_cue(observation)
        if target is None:
            return ActionMessage(observation.step_id, [0.0, 0.0], latency_ms=0.0)

        pose = observation.robot_pose
        distance = math.hypot(target[0] - pose.x, target[1] - pose.y)
        stop_distance = (
            observation.public_goal.stop_distance_m
            if observation.public_goal and observation.public_goal.stop_distance_m is not None
            else 0.8
        )
        if distance <= stop_distance:
            return ActionMessage(observation.step_id, [0.0, 0.0], latency_ms=0.0)

        heading_error = _wrap_angle(math.atan2(target[1] - pose.y, target[0] - pose.x) - pose.yaw)
        yaw_rate = max(-2.0, min(2.0, 3.0 * heading_error))
        linear_velocity = min(0.7, max(0.08, distance - stop_distance))
        if abs(heading_error) > 1.0:
            linear_velocity = 0.06
        return ActionMessage(observation.step_id, [linear_velocity, yaw_rate], latency_ms=0.0)


def _target_after_public_cue(observation: EpisodeObservation) -> tuple[float, float] | None:
    goal = observation.public_goal
    if goal is None or goal.target_human_id is None:
        return None
    target = next(
        (entity for entity in observation.visible_entities if entity.id == goal.target_human_id),
        None,
    )
    if target is None or target.role != "target":
        return None
    return target.x, target.y


def _wrap_angle(value: float) -> float:
    return math.atan2(math.sin(value), math.cos(value))

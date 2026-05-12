from __future__ import annotations

from asimovbm_server.agents.social_cue_navigation import SocialCueNavigationPolicy
from asimovbm_server.episodes import EpisodeObservation, GoalDefinition, Pose2D, PublicEntityObservation


def test_social_cue_policy_stops_before_target_is_public() -> None:
    policy = SocialCueNavigationPolicy()
    observation = EpisodeObservation(
        episode_id="e",
        step_id=0,
        time_s=0.0,
        dt=0.05,
        robot_pose=Pose2D(0.0, 0.0, 0.0),
        robot_velocity=(0.0, 0.0, 0.0),
        public_goal=None,
        visible_entities=(PublicEntityObservation("target", "human", 3.0, 0.0, 0.35, role="human"),),
    )

    action = policy.act(observation)

    assert action.action == [0.0, 0.0]


def test_social_cue_policy_targets_revealed_public_target() -> None:
    policy = SocialCueNavigationPolicy()
    observation = EpisodeObservation(
        episode_id="e",
        step_id=4,
        time_s=1.0,
        dt=0.05,
        robot_pose=Pose2D(0.0, 0.0, 0.0),
        robot_velocity=(0.0, 0.0, 0.0),
        public_goal=GoalDefinition(target_human_id="target", stop_distance_m=0.8),
        visible_entities=(PublicEntityObservation("target", "human", 3.0, 0.0, 0.35, role="target"),),
    )

    action = policy.act(observation)

    assert action.action[0] > 0.0
    assert abs(action.action[1]) < 1e-9

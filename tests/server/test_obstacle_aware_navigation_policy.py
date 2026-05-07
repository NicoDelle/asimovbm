from __future__ import annotations

from asimovbm_server.agents import ObstacleAwareNavigationPolicy
from asimovbm_server.episodes import (
    EpisodeObservation,
    GoalDefinition,
    Pose2D,
    PublicEntityObservation,
)


def test_obstacle_aware_policy_steers_away_from_blocking_obstacle() -> None:
    observation = EpisodeObservation(
        episode_id="obstacle_slalom_001",
        step_id=0,
        time_s=0.0,
        dt=0.05,
        robot_pose=Pose2D(0.0, 0.0, 0.0),
        robot_velocity=(0.0, 0.0, 0.0),
        public_goal=GoalDefinition(x=4.0, y=0.0),
        visible_entities=(
            PublicEntityObservation(
                id="box_left",
                kind="obstacle",
                x=1.4,
                y=0.2,
                radius=0.25,
                role="obstacle",
            ),
        ),
    )

    action = ObstacleAwareNavigationPolicy().act(observation)

    assert action.action[0] > 0.0
    assert abs(action.action[1]) > 0.1

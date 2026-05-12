from __future__ import annotations

from pathlib import Path

from asimovbm_server.episodes import load_episode_pack
from asimovbm_server.episodes.registry import default_scenario_registry
from asimovbm_server.episodes.static_obstacles import (
    StaticObstacleNavigationScenario,
    StaticObstacleWorld,
)
from asimovbm_server.robots import FakeMobileBaseRobot


def test_obstacle_navigation_uses_static_g1_slam_scenario() -> None:
    pack = load_episode_pack(Path("examples/episode_packs/social_navigation_mvp.json"))
    episode = pack.tiers[0].episodes[0]

    scenario = default_scenario_registry().create(episode)

    assert isinstance(scenario, StaticObstacleNavigationScenario)


def test_static_obstacle_observation_uses_g1_slam_lidar_world() -> None:
    pack = load_episode_pack(Path("examples/episode_packs/social_navigation_mvp.json"))
    episode = pack.tiers[0].episodes[0]
    scenario = StaticObstacleNavigationScenario(episode)
    world = scenario.create_world()
    robot = FakeMobileBaseRobot()

    observation = scenario.reset(world, robot)

    assert isinstance(world, StaticObstacleWorld)
    assert observation.metadata["source"] == "g1_slam"
    assert len(observation.range_readings) == 31
    assert min(observation.range_readings) < observation.metadata["lidar_max_range"]
    assert {entity.id for entity in observation.visible_entities} == {"box_left", "box_right"}


def test_static_obstacle_trace_sample_includes_collision_and_world_metadata() -> None:
    pack = load_episode_pack(Path("examples/episode_packs/social_navigation_mvp.json"))
    episode = pack.tiers[0].episodes[0]
    scenario = StaticObstacleNavigationScenario(episode)
    world = scenario.create_world()
    robot = FakeMobileBaseRobot()
    scenario.reset(world, robot)

    sample = scenario.trace_sample(0.0, world, robot)

    assert sample.metadata["source"] == "g1_slam"
    assert set(sample.metadata["obstacle_rects"]) == {"box_left", "box_right"}
    assert sample.collision_summary["source"] == "g1_slam"
    assert sample.distance_to_goal == 4.0

from __future__ import annotations

from pathlib import Path

from asimovbm_server.benchmarks import BenchmarkRunConfig, EpisodicValidationRunner
from asimovbm_server.episodes import load_episode_pack
from asimovbm_server.episodes.dynamic_obstacles import DynamicObstacleNavigationScenario
from asimovbm_server.robots import FakeMobileBaseRobot


def _dynamic_episode(seed: int | None = None):
    pack = load_episode_pack(Path("examples/episode_packs/social_navigation_mvp.json"))
    episode = pack.tiers[1].episodes[0]
    if seed is None:
        return episode
    return type(episode)(
        id=episode.id,
        scenario_type=episode.scenario_type,
        robot_start=episode.robot_start,
        goal=episode.goal,
        max_steps=episode.max_steps,
        control_dt=episode.control_dt,
        bounds=episode.bounds,
        metadata={**episode.metadata, "dynamic_seed": seed},
    )


def test_dynamic_scenario_reset_emits_start_goal_and_entities() -> None:
    scenario = DynamicObstacleNavigationScenario(_dynamic_episode())
    world = scenario.create_world()
    robot = FakeMobileBaseRobot()

    observation = scenario.reset(world, robot)

    assert observation.robot_pose.x == -6.0
    assert observation.public_goal.x == 10.0
    assert len(observation.visible_entities) == 8
    assert all(entity.velocity for entity in observation.visible_entities)


def test_dynamic_seed_is_deterministic_and_changes_trajectory_phase() -> None:
    scenario_a = DynamicObstacleNavigationScenario(_dynamic_episode(seed=7))
    scenario_b = DynamicObstacleNavigationScenario(_dynamic_episode(seed=7))
    scenario_c = DynamicObstacleNavigationScenario(_dynamic_episode(seed=13))
    world_a = scenario_a.create_world()
    world_b = scenario_b.create_world()
    world_c = scenario_c.create_world()

    scenario_a.before_step(2.0, world_a)
    scenario_b.before_step(2.0, world_b)
    scenario_c.before_step(2.0, world_c)

    assert world_a.positions == world_b.positions
    assert set(world_a.positions) == set(world_c.positions)
    assert world_a.positions != world_c.positions


def test_runner_trace_includes_dynamic_entities_every_step() -> None:
    pack = load_episode_pack(Path("examples/episode_packs/social_navigation_mvp.json"))

    result = EpisodicValidationRunner().run(
        pack,
        BenchmarkRunConfig(tier_id="human_obstacles", episode_id="dynamic_crossing_001"),
    )

    record = result.records[0]
    assert record.trace.technical_valid
    assert record.trace.steps
    assert all(step.entities for step in record.trace.steps)
    assert all(step.entities[0].velocity != (0.0, 0.0) for step in record.trace.steps[:5])

from __future__ import annotations

from pathlib import Path

from asimovbm_protocol import ActionMessage
from asimovbm_server.episodes import EpisodeStatusCode, Pose2D, load_episode_pack
from asimovbm_server.episodes.social_cue_target import SocialCueTargetScenario
from asimovbm_server.robots import FakeMobileBaseRobot


def _scenario():
    pack = load_episode_pack(Path("examples/episode_packs/social_navigation_mvp.json"))
    return SocialCueTargetScenario(pack.tiers[2].episodes[0])


def test_observation_hides_target_identity_until_cue() -> None:
    scenario = _scenario()
    world = scenario.create_world()
    robot = FakeMobileBaseRobot()

    before = scenario.reset(world, robot)
    scenario.before_step(1.0, world)
    after = scenario.observe(1.0, world, robot)

    before_target = next(entity for entity in before.visible_entities if entity.id == "target")
    after_target = next(entity for entity in after.visible_entities if entity.id == "target")
    assert before.public_goal is None
    assert before_target.role == "human"
    assert after.public_goal.target_human_id == "target"
    assert after_target.role == "target"
    assert after.active_cues[0].source == "target"


def test_reaching_target_before_cue_does_not_count_as_success() -> None:
    scenario = _scenario()
    world = scenario.create_world()
    robot = FakeMobileBaseRobot()
    scenario.reset(world, robot)
    robot.reset(Pose2D(2.5, 0.4, 0.0))

    status = scenario.evaluate(0.5, world, robot)

    assert status.code == EpisodeStatusCode.RUNNING


def test_stopping_near_target_after_cue_returns_success() -> None:
    scenario = _scenario()
    world = scenario.create_world()
    robot = FakeMobileBaseRobot()
    scenario.reset(world, robot)
    scenario.before_step(1.0, world)
    robot.reset(Pose2D(2.5, 0.4, 0.0))
    robot.apply_action(ActionMessage(0, [0.0, 0.0], latency_ms=0.0), 0.05)

    status = scenario.evaluate(1.05, world, robot)

    assert status.code == EpisodeStatusCode.SUCCESS

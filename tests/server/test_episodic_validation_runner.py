from __future__ import annotations

from pathlib import Path

from asimovbm_protocol import ActionMessage
from asimovbm_server.agents import AgentRegistry, ReferenceSocialNavigationPolicy
from asimovbm_server.benchmarks import BenchmarkRunConfig, EpisodicValidationRunner
from asimovbm_server.episodes import load_episode_pack


def test_local_validation_runner_executes_three_nested_episode_records() -> None:
    pack = load_episode_pack(Path("examples/episode_packs/social_navigation_mvp.json"))

    result = EpisodicValidationRunner().run(
        pack,
        BenchmarkRunConfig(max_attempts_per_episode=1),
    )

    assert [summary.tier_id for summary in result.tier_summaries] == [
        "obstacle_only",
        "human_obstacles",
        "social_cue_target",
    ]
    assert result.attempts == 3
    assert len(result.records) == 3
    assert all(record.trace.steps for record in result.records)
    assert set(result.final_axes) == {
        "perceived_dexterity",
        "perceived_safety",
        "perceived_social_awareness",
        "impression",
    }


def test_social_cue_target_identity_is_hidden_until_cue() -> None:
    pack = load_episode_pack(Path("examples/episode_packs/social_navigation_mvp.json"))

    result = EpisodicValidationRunner().run(
        pack,
        BenchmarkRunConfig(max_attempts_per_episode=1),
    )

    social_record = next(record for record in result.records if record.tier_id == "social_cue_target")
    first_step_observation = social_record.trace.steps[0].observation
    after_cue_observation = next(
        step.observation
        for step in social_record.trace.steps
        if step.observation.active_cues
    )

    assert first_step_observation.public_goal is None
    assert after_cue_observation.public_goal.target_human_id == "target"


def test_local_validation_runner_can_filter_to_one_episode() -> None:
    pack = load_episode_pack(Path("examples/episode_packs/social_navigation_mvp.json"))

    result = EpisodicValidationRunner().run(
        pack,
        BenchmarkRunConfig(tier_id="obstacle_only", episode_id="obstacle_slalom_001"),
    )

    assert result.attempts == 1
    assert len(result.records) == 1
    assert result.records[0].tier_id == "obstacle_only"
    assert result.records[0].episode_id == "obstacle_slalom_001"


def test_dynamic_episode_reports_static_rectangles_and_dynamic_entities() -> None:
    pack = load_episode_pack(Path("examples/episode_packs/social_navigation_mvp.json"))

    result = EpisodicValidationRunner().run(
        pack,
        BenchmarkRunConfig(tier_id="human_obstacles", episode_id="dynamic_crossing_001"),
    )

    first_step = result.records[0].trace.steps[0]
    entity_ids = {entity.id for entity in first_step.entities}
    assert {"static_box_left", "static_box_right"} <= entity_ids
    assert any(entity.id.startswith("blue_cylinder_") for entity in first_step.entities)
    assert first_step.collision_summary["static_collisions"] == []


def test_technical_policy_failure_retries_episode_attempt() -> None:
    class FailingOncePolicy:
        id = "failing-once"
        calls = 0

        def act(self, observation):
            type(self).calls += 1
            if type(self).calls == 1:
                raise RuntimeError("policy boot failed")
            return ActionMessage(observation.step_id, [0.5, 0.0], latency_ms=0.0)

    agent_registry = AgentRegistry()
    agent_registry.register("failing-once", FailingOncePolicy)
    agent_registry.register(ReferenceSocialNavigationPolicy.id, ReferenceSocialNavigationPolicy)
    pack = load_episode_pack(Path("examples/episode_packs/social_navigation_mvp.json"))
    first_tier_pack = type(pack)(
        id=pack.id,
        version=pack.version,
        tiers=(pack.tiers[0],),
        metadata=pack.metadata,
    )

    result = EpisodicValidationRunner(agent_registry=agent_registry).run(
        first_tier_pack,
        BenchmarkRunConfig(agent_id="failing-once", max_attempts_per_episode=2),
    )

    assert result.attempts == 2
    assert result.valid_episodes == 1
    assert not result.records[0].trace.technical_valid
    assert result.records[1].trace.technical_valid

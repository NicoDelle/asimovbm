from __future__ import annotations

from pathlib import Path

from asimovbm_server.episodes import (
    load_episode_pack,
    robojudo_navigation_pack_mapping,
)


def test_robojudo_episode_pack_loads_three_robot_neutral_episodes() -> None:
    pack = load_episode_pack(Path("examples/episode_packs/robojudo_navigation_validation.json"))

    assert [tier.id for tier in pack.tiers] == [
        "approach_user",
        "lateral_open",
        "static_dynamic_obstacles",
    ]
    assert [tier.episodes[0].id for tier in pack.tiers] == [
        "approach_user",
        "lateral_open",
        "lateral_static_dynamic_obstacles",
    ]
    assert {episode.scenario_type for tier in pack.tiers for episode in tier.episodes} == {
        "obstacle_navigation",
        "human_obstacle_navigation",
    }


def test_robojudo_normalizer_keeps_robot_specific_policy_out_of_episode_id() -> None:
    mapping = robojudo_navigation_pack_mapping()
    episode_ids = {
        episode["id"]
        for tier in mapping["tiers"]
        for episode in tier["episodes"]
    }

    assert episode_ids == {
        "approach_user",
        "lateral_open",
        "lateral_static_dynamic_obstacles",
    }
    assert all("g1_" not in episode_id and "go2_" not in episode_id for episode_id in episode_ids)
    dynamic_episode = mapping["tiers"][2]["episodes"][0]
    assert dynamic_episode["metadata"]["dynamic_seed"] == 11
    assert dynamic_episode["metadata"]["dynamic_count"] == 3
    assert dynamic_episode["obstacles"][0]["shape"] == "rectangle"

from __future__ import annotations

import pytest

from asimovbm_server.episodes import (
    EpisodePackError,
    episode_pack_from_mapping,
    validate_episode_pack,
)


def _pack_data():
    return {
        "version": 1,
        "id": "mvp",
        "tiers": [
            {
                "id": "obstacle_only",
                "episodes": [
                    {
                        "id": "obstacle_slalom_001",
                        "scenario_type": "obstacle_navigation",
                        "robot_start": {"x": 0.0, "y": 0.0, "yaw": 0.0},
                        "goal": {"x": 4.0, "y": 0.0},
                        "obstacles": [{"id": "box", "x": 1.0, "y": 0.0, "radius": 0.2}],
                    }
                ],
            },
            {
                "id": "human_obstacles",
                "episodes": [
                    {
                        "id": "static_bystanders_001",
                        "scenario_type": "human_obstacle_navigation",
                        "robot_start": {"x": 0.0, "y": 0.0},
                        "goal": {"x": 4.0, "y": 0.0},
                        "humans": [{"id": "human_a", "x": 2.0, "y": 0.4, "radius": 0.35}],
                    }
                ],
            },
            {
                "id": "social_cue_target",
                "episodes": [
                    {
                        "id": "come_here_001",
                        "scenario_type": "social_cue_target_approach",
                        "robot_start": {"x": 0.0, "y": 0.0},
                        "goal": {"target_human_id": "target", "stop_distance_m": 0.8},
                        "humans": [{"id": "target", "x": 3.0, "y": 0.2, "radius": 0.35}],
                        "cues": [{"time_s": 1.0, "type": "come_here", "source": "target"}],
                    }
                ],
            },
        ],
    }


def test_episode_pack_loads_three_mvp_tiers_from_mapping() -> None:
    pack = episode_pack_from_mapping(_pack_data())
    validate_episode_pack(pack)

    assert [tier.id for tier in pack.tiers] == [
        "obstacle_only",
        "human_obstacles",
        "social_cue_target",
    ]
    assert pack.tiers[2].episodes[0].goal.target_human_id == "target"


def test_rectangle_obstacle_loads_from_center_extents() -> None:
    data = _pack_data()
    obstacle = data["tiers"][0]["episodes"][0]["obstacles"][0]
    obstacle.pop("radius")
    obstacle.update({"shape": "rectangle", "half_width": 0.2, "half_depth": 0.5})

    pack = episode_pack_from_mapping(data)
    validate_episode_pack(pack)

    loaded = pack.tiers[0].episodes[0].obstacles[0]
    assert loaded.shape == "rectangle"
    assert loaded.half_width == 0.2
    assert loaded.half_depth == 0.5
    assert loaded.radius > 0.5


def test_rectangle_obstacle_loads_from_bounds() -> None:
    data = _pack_data()
    data["tiers"][0]["episodes"][0]["obstacles"][0] = {
        "id": "box",
        "x_min": -1.0,
        "y_min": -0.5,
        "x_max": 1.0,
        "y_max": 0.5,
    }

    pack = episode_pack_from_mapping(data)
    validate_episode_pack(pack)

    loaded = pack.tiers[0].episodes[0].obstacles[0]
    assert loaded.x == 0.0
    assert loaded.y == 0.0
    assert loaded.shape == "rectangle"
    assert loaded.half_width == 1.0
    assert loaded.half_depth == 0.5


def test_duplicate_entity_ids_fail_validation() -> None:
    data = _pack_data()
    episode = data["tiers"][1]["episodes"][0]
    episode["humans"].append({"id": "human_a", "x": 2.5, "y": -0.4, "radius": 0.35})

    pack = episode_pack_from_mapping(data)

    with pytest.raises(EpisodePackError, match="duplicate entity id"):
        validate_episode_pack(pack)


def test_missing_social_cue_target_fails_validation() -> None:
    data = _pack_data()
    data["tiers"][2]["episodes"][0]["goal"]["target_human_id"] = "missing"

    pack = episode_pack_from_mapping(data)

    with pytest.raises(EpisodePackError, match="goal target missing"):
        validate_episode_pack(pack)

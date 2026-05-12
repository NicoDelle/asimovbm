from __future__ import annotations

from pathlib import Path

import pytest

from asimovbm_server.benchmarks import BenchmarkRunConfig, EpisodicValidationRunner
from asimovbm_server.episodes import load_episode_pack


def test_two_robot_profiles_one_episode_produce_two_records() -> None:
    pack = load_episode_pack(Path("examples/episode_packs/social_navigation_mvp.json"))

    result = EpisodicValidationRunner().run(
        pack,
        BenchmarkRunConfig(
            tier_id="obstacle_only",
            episode_id="obstacle_slalom_001",
            robot_profile_ids=("minimal-mobile-base", "go2-kinematic"),
        ),
    )

    assert len(result.records) == 2
    assert [record.robot_profile_id for record in result.records] == [
        "minimal-mobile-base",
        "go2-kinematic",
    ]
    assert all(record.trace.robot_profile_id == record.robot_profile_id for record in result.records)
    assert all("asset_backed" in record.robot_metadata for record in result.records)


def test_empty_robot_matrix_selection_fails_validation() -> None:
    pack = load_episode_pack(Path("examples/episode_packs/social_navigation_mvp.json"))

    with pytest.raises(ValueError, match="at least one robot profile"):
        EpisodicValidationRunner().run(
            pack,
            BenchmarkRunConfig(robot_profile_id="", robot_profile_ids=()),
        )

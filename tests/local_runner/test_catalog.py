from __future__ import annotations

import pytest

from asimovbm.local_runner import DEFAULT_EPISODE_IDS, load_default_catalog
from asimovbm.local_runner.catalog import EpisodeCatalogError


def test_default_catalog_loads_exactly_the_six_g1_slam_episodes() -> None:
    catalog = load_default_catalog()

    assert catalog.episode_ids == DEFAULT_EPISODE_IDS
    assert len(catalog) == 6
    assert [spec.id for spec in catalog] == list(DEFAULT_EPISODE_IDS)


def test_catalog_preserves_robot_and_backend_selectors() -> None:
    catalog = load_default_catalog()

    assert catalog.get("g1_approach_user").robot_selector == "official_g1"
    assert catalog.get("g1_approach_user").robot_id == "g1"
    assert catalog.get("g1_approach_user").policy_id == "g1_robojudo_asap"
    assert catalog.get("g1_approach_user").canonical_backend_id == "g1_robojudo"
    assert catalog.get("go2_lateral_open").robot_selector == "official_go2"
    assert catalog.get("go2_lateral_open").robot_id == "go2"
    assert catalog.get("go2_lateral_open").policy_id == "go2_unitree_rl_mjlab"
    assert catalog.get("go2_lateral_open").canonical_backend_id == "go2_mujoco_onnx"
    assert catalog.get("g1_lateral_static_dynamic_obstacles").checksum_sha256


def test_catalog_selects_one_robot_at_a_time_with_default_policy() -> None:
    catalog = load_default_catalog()

    g1_specs = catalog.select(robot_id="g1")
    go2_specs = catalog.select(robot_id="go2")

    assert [spec.id for spec in g1_specs] == [
        "g1_approach_user",
        "g1_lateral_open",
        "g1_lateral_static_dynamic_obstacles",
    ]
    assert {spec.policy_id for spec in g1_specs} == {"g1_robojudo_asap"}
    assert [spec.id for spec in go2_specs] == [
        "go2_approach_user",
        "go2_lateral_open",
        "go2_lateral_static_dynamic_obstacles",
    ]
    assert {spec.policy_id for spec in go2_specs} == {"go2_unitree_rl_mjlab"}


def test_catalog_rejects_cross_robot_episode_selection() -> None:
    catalog = load_default_catalog()

    with pytest.raises(EpisodeCatalogError):
        catalog.select(("go2_approach_user",), robot_id="g1")


def test_policy_path_override_is_applied_to_selected_specs() -> None:
    catalog = load_default_catalog()

    specs = catalog.select(
        ("go2_approach_user",),
        robot_id="go2",
        policy_id="go2_unitree_rl_mjlab",
        policy_path="policies/go2/custom.onnx",
    )

    assert specs[0].config.locomotion.policy_path.as_posix() == "policies/go2/custom.onnx"

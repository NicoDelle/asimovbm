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

    assert catalog.get("g1_point_to_point_open").robot_selector == "official_g1"
    assert catalog.get("g1_point_to_point_open").robot_id == "g1"
    assert catalog.get("g1_point_to_point_open").policy_id == "g1_robojudo_asap"
    assert catalog.get("g1_point_to_point_open").canonical_backend_id == "g1_robojudo"
    assert catalog.get("go2_point_to_point_static_obstacles").robot_selector == "official_go2"
    assert catalog.get("go2_point_to_point_static_obstacles").robot_id == "go2"
    assert catalog.get("go2_point_to_point_static_obstacles").policy_id == "go2_unitree_rl_mjlab"
    assert catalog.get("go2_point_to_point_static_obstacles").canonical_backend_id == "go2_mujoco_onnx"
    assert catalog.get("g1_point_to_point_dynamic_npcs").checksum_sha256
    assert catalog.get("g1_point_to_point_dynamic_npcs").raw_config["world"]["obstacles"] == []


def test_catalog_selects_one_robot_at_a_time_with_default_policy() -> None:
    catalog = load_default_catalog()

    g1_specs = catalog.select(robot_id="g1")
    go2_specs = catalog.select(robot_id="go2")

    assert [spec.id for spec in g1_specs] == [
        "g1_point_to_point_open",
        "g1_point_to_point_static_obstacles",
        "g1_point_to_point_dynamic_npcs",
    ]
    assert {spec.policy_id for spec in g1_specs} == {"g1_robojudo_asap"}
    assert [spec.id for spec in go2_specs] == [
        "go2_point_to_point_open",
        "go2_point_to_point_static_obstacles",
        "go2_point_to_point_dynamic_npcs",
    ]
    assert {spec.policy_id for spec in go2_specs} == {"go2_unitree_rl_mjlab"}


def test_catalog_can_select_second_g1_robojudo_policy() -> None:
    catalog = load_default_catalog()

    specs = catalog.select(
        ("g1_point_to_point_open",),
        robot_id="g1",
        policy_id="g1_robojudo_unitree",
    )

    assert specs[0].policy_id == "g1_robojudo_unitree"
    assert specs[0].config.locomotion.mode == "robojudo"
    assert specs[0].config.locomotion.robojudo_config == "g1"
    assert specs[0].canonical_backend_id == "g1_robojudo"


def test_catalog_rejects_cross_robot_episode_selection() -> None:
    catalog = load_default_catalog()

    with pytest.raises(EpisodeCatalogError):
        catalog.select(("go2_point_to_point_open",), robot_id="g1")


def test_policy_path_override_is_applied_to_selected_specs() -> None:
    catalog = load_default_catalog()

    specs = catalog.select(
        ("go2_point_to_point_open",),
        robot_id="go2",
        policy_id="go2_unitree_rl_mjlab",
        policy_path="policies/go2/custom.onnx",
    )

    assert specs[0].config.locomotion.policy_path.as_posix() == "policies/go2/custom.onnx"


def test_g1_unitree_robojudo_policy_profile_is_available() -> None:
    catalog = load_default_catalog()

    specs = catalog.select(
        ("g1_point_to_point_open",),
        robot_id="g1",
        policy_id="g1_robojudo_unitree",
    )

    assert specs[0].policy_id == "g1_robojudo_unitree"
    assert specs[0].config.locomotion.robojudo_config == "g1"

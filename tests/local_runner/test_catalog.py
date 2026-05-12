from __future__ import annotations

from asimovbm.local_runner import DEFAULT_EPISODE_IDS, load_default_catalog


def test_default_catalog_loads_exactly_the_six_g1_slam_episodes() -> None:
    catalog = load_default_catalog()

    assert catalog.episode_ids == DEFAULT_EPISODE_IDS
    assert len(catalog) == 6
    assert [spec.id for spec in catalog] == list(DEFAULT_EPISODE_IDS)


def test_catalog_preserves_robot_and_backend_selectors() -> None:
    catalog = load_default_catalog()

    assert catalog.get("g1_approach_user").robot_selector == "official_g1"
    assert catalog.get("g1_approach_user").canonical_backend_id == "g1_robojudo"
    assert catalog.get("go2_lateral_open").robot_selector == "official_go2"
    assert catalog.get("go2_lateral_open").canonical_backend_id == "go2_mujoco_onnx"
    assert catalog.get("g1_lateral_static_dynamic_obstacles").checksum_sha256


def test_catalog_exposes_role_inventory_for_all_six_episodes() -> None:
    catalog = load_default_catalog()

    inventories = {spec.id: spec.role_inventory for spec in catalog}

    assert all(isinstance(inventory, tuple) for inventory in inventories.values())
    assert any(role["role"] == "target" for role in inventories["g1_approach_user"])
    assert any(role["role"] == "target" for role in inventories["go2_approach_user"])
    assert inventories["g1_lateral_open"] == ()
    assert inventories["go2_lateral_open"] == ()
    assert sum(1 for role in inventories["g1_lateral_static_dynamic_obstacles"] if role["role"] == "bystander") == 3
    assert sum(1 for role in inventories["go2_lateral_static_dynamic_obstacles"] if role["role"] == "bystander") == 3

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

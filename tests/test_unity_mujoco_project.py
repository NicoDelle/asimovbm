from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_EPISODES = REPO_ROOT / "g1_slam" / "config" / "episodes"
UNITY_EPISODES = (
    REPO_ROOT
    / "unity_mujoco_slam"
    / "Assets"
    / "AsimovMujoco"
    / "Resources"
    / "Episodes"
)
UNITY_GENERATED_MJCF = (
    REPO_ROOT
    / "unity_mujoco_slam"
    / "Assets"
    / "AsimovMujoco"
    / "GeneratedMjcf"
)
UNITY_SCENES = REPO_ROOT / "unity_mujoco_slam" / "Assets" / "AsimovMujoco" / "Scenes"

EPISODE_IDS = (
    "g1_lateral_open",
    "g1_lateral_static_dynamic_obstacles",
    "g1_approach_user",
    "go2_lateral_open",
    "go2_lateral_static_dynamic_obstacles",
    "go2_approach_user",
)


def test_unity_project_keeps_all_current_g1_and_go2_episode_configs() -> None:
    for episode_id in EPISODE_IDS:
        source = json.loads((SOURCE_EPISODES / f"{episode_id}.json").read_text(encoding="utf-8"))
        unity = json.loads((UNITY_EPISODES / f"{episode_id}.json").read_text(encoding="utf-8"))

        assert unity == source


def test_unity_robot_policy_catalog_preserves_current_policy_choices() -> None:
    catalog_path = (
        REPO_ROOT
        / "unity_mujoco_slam"
        / "Assets"
        / "AsimovMujoco"
        / "Resources"
        / "RobotPolicies"
        / "robot_policy_catalog.json"
    )
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    robots = {entry["robot_id"]: entry for entry in catalog["robots"]}

    assert robots["g1"]["locomotion_mode"] == "robojudo"
    assert robots["g1"]["policy_provider"] == "external_robojudo"
    assert robots["g1"]["robojudo_config"] == "g1_asap_loco"

    assert robots["go2"]["locomotion_mode"] == "policy"
    assert robots["go2"]["policy_provider"] == "onnx"
    assert robots["go2"]["policy_path"] == "../g1_slam/policies/go2/unitree_rl_mjlab/policy.onnx"
    assert robots["go2"]["observation_profile"] == "dias_ai_master_go2_velocity_flat"
    assert robots["go2"]["observation_size"] == 45
    assert robots["go2"]["action_scale"] == 0.5


def test_unity_manifest_declares_mujoco_package() -> None:
    manifest_path = REPO_ROOT / "unity_mujoco_slam" / "Packages" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert "org.mujoco" in manifest["dependencies"]
    assert "google-deepmind/mujoco.git?path=/unity#3.7.0" in manifest["dependencies"]["org.mujoco"]
    assert manifest["dependencies"]["com.unity.modules.physics"] == "1.0.0"
    assert manifest["dependencies"]["com.unity.modules.terrain"] == "1.0.0"
    assert manifest["dependencies"]["com.unity.modules.imageconversion"] == "1.0.0"


def test_generated_mjcf_files_are_expanded_episode_scenes() -> None:
    for episode_id in EPISODE_IDS:
        mjcf_path = UNITY_GENERATED_MJCF / f"{episode_id}.xml"
        assert mjcf_path.exists()

        mjcf = mjcf_path.read_text(encoding="utf-8")
        assert "<include" not in mjcf
        assert "meshdir=" in mjcf
        assert 'name="nav_floor"' in mjcf
        assert 'name="goal"' in mjcf


def test_generated_mjcf_files_compile_with_mujoco() -> None:
    mujoco = pytest.importorskip("mujoco")
    expected_actuators = {
        "g1": 29,
        "go2": 12,
    }

    for episode_id in EPISODE_IDS:
        model = mujoco.MjModel.from_xml_path(str(UNITY_GENERATED_MJCF / f"{episode_id}.xml"))
        robot_id = episode_id.split("_", 1)[0]

        assert model.nu == expected_actuators[robot_id]
        assert model.nbody >= (31 if robot_id == "g1" else 18)


def test_committed_launcher_scene_does_not_keep_old_capsule_robot_proxy() -> None:
    launcher_scene = UNITY_SCENES / "AsimovMujocoEpisodes.unity"
    if not launcher_scene.exists():
        return

    scene_text = launcher_scene.read_text(encoding="utf-8")
    assert "RobotProxy" not in scene_text

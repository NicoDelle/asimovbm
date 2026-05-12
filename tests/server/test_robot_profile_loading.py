from __future__ import annotations

import json
from pathlib import Path

import pytest

from asimovbm_server.robots import (
    RobotProfileSetupError,
    default_robot_registry,
    load_robot_profiles,
)
from asimovbm_server.robots.mujoco_kinematic import KinematicMuJoCoRobot
from asimovbm_server.robots.registry import RobotRegistry


def test_default_robot_profiles_include_validation_variants() -> None:
    registry = default_robot_registry()

    profile_ids = {profile.id for profile in registry.profiles()}

    assert {"minimal-mobile-base", "g1-kinematic", "g1-robojudo", "go2-kinematic"} <= profile_ids
    assert registry.profile("g1-kinematic").asset_backed is True
    assert registry.profile("g1-robojudo").adapter_kind == "robojudo"
    assert registry.profile("go2-kinematic").marker_only is True


def test_g1_profile_creates_kinematic_adapter_with_expected_metadata() -> None:
    robot = default_robot_registry().create("g1-kinematic")

    assert robot.profile.id == "g1-kinematic"
    assert robot.profile.embodiment_kind == "humanoid"
    assert robot.profile.action_mode == "mobile_base_velocity"
    assert robot.profile.body_radius == pytest.approx(0.28)


def test_missing_asset_backed_profile_fails_with_setup_diagnostic(tmp_path: Path) -> None:
    config = tmp_path / "profiles.json"
    config.write_text(
        json.dumps(
            {
                "profiles": [
                    {
                        "id": "missing-g1",
                        "embodiment_kind": "humanoid",
                        "model_path": "missing.xml",
                        "asset_backed": True,
                        "marker_only": False,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    profile = load_robot_profiles(config)[0]
    registry = RobotRegistry()
    registry.register_factory("humanoid", KinematicMuJoCoRobot)
    registry.register_profile(profile)

    with pytest.raises(RobotProfileSetupError, match="missing-g1.*missing.xml"):
        registry.create("missing-g1")


def test_unknown_profile_fails_before_episode_loop() -> None:
    with pytest.raises(KeyError, match="unknown robot profile"):
        default_robot_registry().validate_profile_ids(("does-not-exist",))


def test_robojudo_profile_fails_with_setup_diagnostic_when_assets_missing() -> None:
    with pytest.raises(RobotProfileSetupError, match="g1-robojudo.*RoboJudo checkout"):
        default_robot_registry().create("g1-robojudo")

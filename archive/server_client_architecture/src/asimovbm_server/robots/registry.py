"""Robot adapter registry for validation runs."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from .base import FakeMobileBaseRobot, RobotAdapter, RobotProfile
from .mujoco_kinematic import KinematicMuJoCoRobot
from .robojudo_adapter import RoboJudoRobot

RobotFactory = Callable[[RobotProfile], RobotAdapter]


class RobotRegistry:
    def __init__(self) -> None:
        self._profiles: dict[str, RobotProfile] = {}
        self._factories: dict[str, RobotFactory] = {}

    def register_profile(self, profile: RobotProfile) -> None:
        self._profiles[profile.id] = profile

    def register_factory(self, embodiment_kind: str, factory: RobotFactory) -> None:
        self._factories[embodiment_kind] = factory

    def create(self, profile_id: str) -> RobotAdapter:
        profile = self._profiles.get(profile_id)
        if profile is None:
            raise KeyError(f"unknown robot profile: {profile_id}")
        factory = self._factories.get(profile.embodiment_kind)
        if factory is None:
            raise KeyError(f"no robot factory for embodiment kind: {profile.embodiment_kind}")
        return factory(profile)

    def profile(self, profile_id: str) -> RobotProfile:
        profile = self._profiles.get(profile_id)
        if profile is None:
            raise KeyError(f"unknown robot profile: {profile_id}")
        return profile

    def profiles(self) -> tuple[RobotProfile, ...]:
        return tuple(self._profiles[profile_id] for profile_id in sorted(self._profiles))

    def validate_profile_ids(self, profile_ids: tuple[str, ...]) -> None:
        if not profile_ids:
            raise ValueError("at least one robot profile id must be selected")
        for profile_id in profile_ids:
            self.profile(profile_id)


def default_robot_registry() -> RobotRegistry:
    registry = RobotRegistry()
    registry.register_factory("mobile_base", lambda profile: FakeMobileBaseRobot(profile))
    registry.register_factory("humanoid", KinematicMuJoCoRobot)
    registry.register_factory("quadruped", KinematicMuJoCoRobot)
    registry.register_factory("robojudo_humanoid", RoboJudoRobot)
    for profile in load_robot_profiles(default_robot_profile_path()):
        registry.register_profile(profile)
    return registry


def default_robot_profile_path() -> Path:
    return Path(__file__).resolve().parents[3] / "examples" / "robot_profiles" / "local_validation.json"


def load_robot_profiles(path: Path) -> tuple[RobotProfile, ...]:
    data = json.loads(path.read_text(encoding="utf-8"))
    root = path.parent.parent.parent
    profiles = []
    for item in data.get("profiles", []):
        model_path = item.get("model_path")
        resolved_model_path = None
        if model_path:
            candidate = Path(model_path)
            resolved_model_path = candidate if candidate.is_absolute() else root / candidate
        profiles.append(
            RobotProfile(
                id=str(item["id"]),
                embodiment_kind=str(item["embodiment_kind"]),
                action_mode=str(item.get("action_mode", "mobile_base_velocity")),
                model_path=resolved_model_path,
                body_radius=float(item.get("body_radius", 0.25)),
                asset_backed=bool(item.get("asset_backed", False)),
                marker_only=bool(item.get("marker_only", not item.get("asset_backed", False))),
                adapter_kind=str(item.get("adapter_kind", "fake_mobile_base")),
                metadata=dict(item.get("metadata", {})),
            )
        )
    return tuple(profiles)

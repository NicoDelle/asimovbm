"""Robot adapter registry for validation runs."""

from __future__ import annotations

from collections.abc import Callable

from .base import FakeMobileBaseRobot, RobotAdapter, RobotProfile

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


def default_robot_registry() -> RobotRegistry:
    registry = RobotRegistry()
    registry.register_factory("mobile_base", lambda profile: FakeMobileBaseRobot(profile))
    registry.register_factory("humanoid", lambda profile: FakeMobileBaseRobot(profile))
    registry.register_factory("quadruped", lambda profile: FakeMobileBaseRobot(profile))
    registry.register_profile(RobotProfile(id="minimal-mobile-base", embodiment_kind="mobile_base"))
    registry.register_profile(RobotProfile(id="placeholder-humanoid", embodiment_kind="humanoid"))
    registry.register_profile(RobotProfile(id="placeholder-robot-dog", embodiment_kind="quadruped"))
    return registry

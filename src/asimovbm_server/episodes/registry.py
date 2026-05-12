"""Scenario factory registry."""

from __future__ import annotations

from collections.abc import Callable

from .dynamic_obstacles import DynamicObstacleNavigationScenario
from .models import EpisodeDefinition, EpisodeScenario
from .social_cue_target import SocialCueTargetScenario
from .static_obstacles import StaticObstacleNavigationScenario

ScenarioFactory = Callable[[EpisodeDefinition], EpisodeScenario]


class ScenarioRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, ScenarioFactory] = {}

    def register(self, scenario_type: str, factory: ScenarioFactory) -> None:
        self._factories[scenario_type] = factory

    def create(self, definition: EpisodeDefinition) -> EpisodeScenario:
        factory = self._factories.get(definition.scenario_type)
        if factory is None:
            raise KeyError(f"unknown scenario type: {definition.scenario_type}")
        return factory(definition)


def default_scenario_registry() -> ScenarioRegistry:
    registry = ScenarioRegistry()
    registry.register("obstacle_navigation", StaticObstacleNavigationScenario)
    registry.register("human_obstacle_navigation", DynamicObstacleNavigationScenario)
    registry.register("dynamic_obstacle_navigation", DynamicObstacleNavigationScenario)
    registry.register("social_cue_target_approach", SocialCueTargetScenario)
    return registry

"""Local agent policy registry."""

from __future__ import annotations

from collections.abc import Callable

from .base import AgentPolicy
from .obstacle_aware_navigation import ObstacleAwareNavigationPolicy
from .reference_social_navigation import ReferenceSocialNavigationPolicy
from .social_cue_navigation import SocialCueNavigationPolicy

AgentFactory = Callable[[], AgentPolicy]


class AgentRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, AgentFactory] = {}

    def register(self, agent_id: str, factory: AgentFactory) -> None:
        self._factories[agent_id] = factory

    def create(self, agent_id: str) -> AgentPolicy:
        factory = self._factories.get(agent_id)
        if factory is None:
            raise KeyError(f"unknown agent policy: {agent_id}")
        return factory()

    def agent_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._factories))


def default_agent_registry() -> AgentRegistry:
    registry = AgentRegistry()
    registry.register(ObstacleAwareNavigationPolicy.id, ObstacleAwareNavigationPolicy)
    registry.register(ReferenceSocialNavigationPolicy.id, ReferenceSocialNavigationPolicy)
    registry.register(SocialCueNavigationPolicy.id, SocialCueNavigationPolicy)
    return registry

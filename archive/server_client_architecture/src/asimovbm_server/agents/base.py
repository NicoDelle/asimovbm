"""Local policy contracts for validation runs."""

from __future__ import annotations

from typing import Protocol

from asimovbm_protocol import ActionMessage
from asimovbm_server.episodes import EpisodeObservation


class AgentPolicy(Protocol):
    id: str

    def act(self, observation: EpisodeObservation) -> ActionMessage:
        ...

"""Trace models for episodic validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from asimovbm_protocol import ActionMessage
from asimovbm_server.episodes import (
    EpisodeDefinition,
    EpisodeObservation,
    EpisodeStatus,
    PublicCueEvent,
    PublicEntityObservation,
)
from asimovbm_server.robots import RobotState


@dataclass(frozen=True)
class StepTrace:
    step_id: int
    time_s: float
    dt: float
    robot_state: RobotState
    action: ActionMessage
    entities: tuple[PublicEntityObservation, ...]
    cue_events: tuple[PublicCueEvent, ...]
    observation: EpisodeObservation
    status_after_step: EpisodeStatus
    collision_summary: dict[str, Any] = field(default_factory=dict)
    distance_to_goal: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EpisodeTrace:
    pack_id: str
    tier_id: str
    episode_id: str
    attempt: int
    definition: EpisodeDefinition
    steps: tuple[StepTrace, ...]
    terminal_status: EpisodeStatus
    robot_profile_id: str
    agent_id: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def technical_valid(self) -> bool:
        return self.terminal_status.technical_valid

    @property
    def behavioral_success(self) -> bool:
        return self.terminal_status.behavioral_success

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

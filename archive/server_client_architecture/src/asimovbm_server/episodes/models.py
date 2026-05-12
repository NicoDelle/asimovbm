"""Episode pack and scenario contract models for local validation runs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any, Protocol


class EpisodePackError(ValueError):
    """Raised when an episode pack cannot be loaded or validated."""


class EpisodeStatusCode(StrEnum):
    RUNNING = "running"
    SUCCESS = "success"
    TIMEOUT = "timeout"
    COLLISION = "collision"
    PROXEMIC_VIOLATION = "proxemic_violation"
    LEFT_BOUNDS = "left_bounds"
    ROBOT_FAILURE = "robot_failure"
    EPISODE_FAILURE = "episode_failure"
    POLICY_FAILURE = "policy_failure"


@dataclass(frozen=True)
class Pose2D:
    x: float
    y: float
    yaw: float = 0.0


@dataclass(frozen=True)
class GoalDefinition:
    x: float | None = None
    y: float | None = None
    target_human_id: str | None = None
    stop_distance_m: float | None = None


@dataclass(frozen=True)
class EntityDefinition:
    id: str
    kind: str
    x: float
    y: float
    radius: float
    role: str | None = None
    posture: str | None = None
    public_before_cue: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CueDefinition:
    time_s: float
    type: str
    source: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EpisodeDefinition:
    id: str
    scenario_type: str
    robot_start: Pose2D
    goal: GoalDefinition | None = None
    obstacles: tuple[EntityDefinition, ...] = ()
    humans: tuple[EntityDefinition, ...] = ()
    cues: tuple[CueDefinition, ...] = ()
    max_steps: int = 200
    control_dt: float = 0.05
    bounds: tuple[float, float, float, float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def entities(self) -> tuple[EntityDefinition, ...]:
        return self.obstacles + self.humans


@dataclass(frozen=True)
class TierDefinition:
    id: str
    episodes: tuple[EpisodeDefinition, ...]
    required_valid_episodes: int | None = None
    max_attempts: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EpisodePack:
    id: str
    version: int
    tiers: tuple[TierDefinition, ...]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PublicEntityObservation:
    id: str
    kind: str
    x: float
    y: float
    radius: float
    role: str | None = None


@dataclass(frozen=True)
class PublicCueEvent:
    time_s: float
    type: str
    source: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EpisodeObservation:
    episode_id: str
    step_id: int
    time_s: float
    dt: float
    robot_pose: Pose2D
    robot_velocity: tuple[float, float, float]
    public_goal: GoalDefinition | None = None
    range_readings: tuple[float, ...] = ()
    visible_entities: tuple[PublicEntityObservation, ...] = ()
    active_cues: tuple[PublicCueEvent, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EpisodeStatus:
    code: EpisodeStatusCode
    technical_valid: bool = True
    reason: str | None = None
    distance_to_goal: float | None = None

    @property
    def terminal(self) -> bool:
        return self.code != EpisodeStatusCode.RUNNING

    @property
    def behavioral_success(self) -> bool:
        return self.code == EpisodeStatusCode.SUCCESS and self.technical_valid


@dataclass(frozen=True)
class ScenarioTraceSample:
    entities: tuple[PublicEntityObservation, ...] = ()
    cue_events: tuple[PublicCueEvent, ...] = ()
    collision_summary: dict[str, Any] = field(default_factory=dict)
    distance_to_goal: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ScenarioWorld(Protocol):
    """Mutable scenario state owned by an episode implementation."""


class EpisodeScenario(Protocol):
    definition: EpisodeDefinition

    def create_world(self) -> ScenarioWorld:
        ...

    def reset(self, world: ScenarioWorld, robot: Any) -> EpisodeObservation:
        ...

    def before_step(self, time_s: float, world: ScenarioWorld) -> None:
        ...

    def observe(self, time_s: float, world: ScenarioWorld, robot: Any) -> EpisodeObservation:
        ...

    def evaluate(self, time_s: float, world: ScenarioWorld, robot: Any) -> EpisodeStatus:
        ...

    def trace_sample(
        self,
        time_s: float,
        world: ScenarioWorld,
        robot: Any,
    ) -> ScenarioTraceSample:
        ...

"""Trace dataclasses emitted by the local episode runner."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

MEASUREMENT_PROOF_LEVELS: tuple[str, ...] = (
    "unavailable",
    "reference",
    "fake_model_data",
    "minimal_mujoco",
    "asset_mujoco",
)


@dataclass(frozen=True)
class LocalStepTrace:
    step_id: int
    time_s: float
    dt_s: float
    robot_pose: tuple[float, float, float]
    robot_velocity: tuple[float, float, float]
    action: tuple[float, float]
    distance_to_goal: float
    lidar_ranges: tuple[float, ...] = ()
    static_entities: tuple[dict[str, Any], ...] = ()
    dynamic_entities: tuple[dict[str, Any], ...] = ()
    collisions: tuple[dict[str, Any], ...] = ()
    social_cues: tuple[dict[str, Any], ...] = ()
    public_observation: dict[str, Any] = field(default_factory=dict)
    qpos: tuple[float, ...] = ()
    qvel: tuple[float, ...] = ()
    measurement_source: str = "reference"
    frame_conventions: dict[str, Any] = field(default_factory=dict)
    robot_state: dict[str, Any] = field(default_factory=dict)
    contacts: tuple[dict[str, Any], ...] = ()
    sensors: dict[str, Any] = field(default_factory=dict)
    status: str = "running"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LocalEpisodeTrace:
    episode_id: str
    iteration: int
    tier_id: str
    technical_valid: bool
    terminal_status: str
    steps: tuple[LocalStepTrace, ...]
    config_checksum_sha256: str
    config_path: str
    robot_selector: str
    canonical_backend_id: str
    execution_backend_id: str
    viewer_mode: str
    measurement_backend_id: str = "reference"
    measurement_proof_level: str = "reference"
    validation_summary: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_s(self) -> float:
        if not self.steps:
            return 0.0
        return self.steps[-1].time_s

    @property
    def final_distance_to_goal(self) -> float | None:
        if not self.steps:
            return None
        return self.steps[-1].distance_to_goal

    @property
    def collision_count(self) -> int:
        return sum(len(step.collisions) for step in self.steps)

    @property
    def technically_failed(self) -> bool:
        return not self.technical_valid

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LocalRunRecord:
    trace: LocalEpisodeTrace
    metrics: dict[str, Any]
    trace_path: str
    metrics_path: str

    def to_manifest_entry(self) -> dict[str, Any]:
        return {
            "episode_id": self.trace.episode_id,
            "iteration": self.trace.iteration,
            "technical_valid": self.trace.technical_valid,
            "terminal_status": self.trace.terminal_status,
            "trace_path": self.trace_path,
            "metrics_path": self.metrics_path,
            "viewer_mode": self.trace.viewer_mode,
            "canonical_backend_id": self.trace.canonical_backend_id,
            "execution_backend_id": self.trace.execution_backend_id,
            "measurement_backend_id": self.trace.measurement_backend_id,
            "measurement_proof_level": self.trace.measurement_proof_level,
            "validation_status": self.trace.validation_summary.get("status"),
        }

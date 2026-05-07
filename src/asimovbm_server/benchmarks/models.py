"""Run-level result models for local episodic validation."""

from __future__ import annotations

from dataclasses import dataclass, field

from asimovbm_server.metrics import MetricValue
from asimovbm_server.traces import EpisodeTrace


@dataclass(frozen=True)
class BenchmarkRunConfig:
    robot_profile_id: str = "minimal-mobile-base"
    agent_id: str = "reference-social-nav"
    max_attempts_per_episode: int = 1
    realtime: float = 0.0
    visible: bool = False


@dataclass(frozen=True)
class EpisodeRunRecord:
    tier_id: str
    episode_id: str
    attempt: int
    trace: EpisodeTrace
    metrics: dict[str, MetricValue] = field(default_factory=dict)


@dataclass(frozen=True)
class TierRunSummary:
    tier_id: str
    attempts: int
    valid_episodes: int
    technical_failures: int
    metric_status_counts: dict[str, int]


@dataclass(frozen=True)
class BenchmarkRunResult:
    pack_id: str
    records: tuple[EpisodeRunRecord, ...]
    tier_summaries: tuple[TierRunSummary, ...]
    final_axes: dict[str, float | None]

    @property
    def attempts(self) -> int:
        return sum(summary.attempts for summary in self.tier_summaries)

    @property
    def valid_episodes(self) -> int:
        return sum(summary.valid_episodes for summary in self.tier_summaries)

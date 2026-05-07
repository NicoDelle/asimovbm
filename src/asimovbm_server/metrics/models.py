"""Metric interface models for episodic validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

from asimovbm_server.traces import EpisodeTrace


class MetricStatus(StrEnum):
    NOT_IMPLEMENTED = "not_implemented"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    COMPUTED = "computed"


@dataclass(frozen=True)
class MetricContext:
    tier_id: str
    episode_id: str
    constants: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MetricValue:
    metric_id: str
    status: MetricStatus
    raw_value: float | None = None
    normalized_score: float | None = None
    confidence: str = "low"
    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class MetricFunction(Protocol):
    id: str
    required_fields: tuple[str, ...]

    def compute(self, trace: EpisodeTrace, context: MetricContext) -> MetricValue:
        ...

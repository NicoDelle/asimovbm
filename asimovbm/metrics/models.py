"""Metric interface models for local episodic validation.

The metric package is intentionally simulator-agnostic. Runner code is
responsible for extracting the narrow input objects required by each metric;
the protocol here only describes the common result envelope and registry-facing
call shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from math import isfinite
from typing import Any, Protocol

SOCIAL_NAVIGATION_AXIS_IDS: tuple[str, ...] = (
    "perceived_dexterity",
    "perceived_safety",
    "perceived_social_awareness",
    "impression",
)

SOCIAL_NAVIGATION_METRIC_IDS: tuple[str, ...] = (
    "task_success_rate",
    "task_completion_time",
    "comfort_aware_path_efficiency",
    "hesitation",
    "min_human_robot_distance",
    "proxemic_intrusion_dose",
    "speed_near_humans_p95",
    "gesture_response_success",
    "acknowledgement_clarity",
    "human_aware_approach",
    "bystander_ack",
    "sparc",
    "heading_jerk",
    "stability",
    "legibility",
    "behavioral_naturalness",
)


class MetricStatus(StrEnum):
    NOT_IMPLEMENTED = "not_implemented"
    NOT_APPLICABLE = "not_applicable"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    INVALID_INPUT = "invalid_input"
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
    confidence: str = "insufficient"
    units: str | None = None
    reason: str | None = None
    raw_inputs_summary: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.normalized_score is not None:
            score = float(self.normalized_score)
            if not isfinite(score) or score < 0.0 or score > 1.0:
                raise ValueError("normalized_score must be finite and in [0, 1]")
        if self.raw_value is not None and not isfinite(float(self.raw_value)):
            raise ValueError("raw_value must be finite when provided")

    @property
    def scored(self) -> bool:
        return (
            self.status == MetricStatus.COMPUTED
            and self.normalized_score is not None
        )


class MetricFunction(Protocol):
    id: str
    required_fields: tuple[str, ...]

    def compute(self, trace: Any, context: MetricContext) -> MetricValue:
        ...

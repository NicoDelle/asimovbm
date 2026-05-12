"""Aggregation for social-navigation metric results."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass

from .models import SOCIAL_NAVIGATION_AXIS_IDS, MetricStatus, MetricValue
from .weights import V0_EVIDENCE_WEIGHTS, normalized_axis_weights


@dataclass(frozen=True)
class AxisScore:
    axis_id: str
    status: MetricStatus
    score: float | None
    confidence: str
    contributing_features: tuple[str, ...]
    omitted_features: tuple[str, ...]
    omitted_feature_statuses: dict[str, str]
    model_metadata: dict[str, str]

    def to_report(self) -> dict[str, object]:
        payload = asdict(self)
        payload["status"] = self.status.value
        return payload


def aggregate_axis(
    metric_values: Mapping[str, MetricValue],
    axis_id: str,
) -> AxisScore:
    weights = normalized_axis_weights(axis_id)
    scored: dict[str, float] = {}
    omitted: list[str] = []
    omitted_statuses: dict[str, str] = {}
    for feature_id in weights:
        value = metric_values.get(feature_id)
        if value is not None and value.scored:
            scored[feature_id] = value.normalized_score or 0.0
        else:
            omitted.append(feature_id)
            omitted_statuses[feature_id] = (
                value.status.value if value is not None else "missing"
            )
    if not scored:
        return AxisScore(
            axis_id=axis_id,
            status=MetricStatus.NOT_APPLICABLE,
            score=None,
            confidence="not_applicable",
            contributing_features=(),
            omitted_features=tuple(omitted),
            omitted_feature_statuses=omitted_statuses,
            model_metadata=_model_metadata(),
        )
    active_weight_total = sum(weights[feature_id] for feature_id in scored)
    score = sum(
        scored[feature_id] * (weights[feature_id] / active_weight_total)
        for feature_id in scored
    )
    confidence = "sufficient" if not omitted else "partial"
    return AxisScore(
        axis_id=axis_id,
        status=MetricStatus.COMPUTED,
        score=score,
        confidence=confidence,
        contributing_features=tuple(scored),
        omitted_features=tuple(omitted),
        omitted_feature_statuses=omitted_statuses,
        model_metadata=_model_metadata(),
    )


def aggregate_axes(metric_values: Mapping[str, MetricValue]) -> dict[str, AxisScore]:
    return {
        axis_id: aggregate_axis(metric_values, axis_id)
        for axis_id in SOCIAL_NAVIGATION_AXIS_IDS
    }


def _model_metadata() -> dict[str, str]:
    return {
        "kind": "manual_v0_evidence_weights",
        "version": "v0",
        "source": "docs/specs/social-navigation-metrics.md",
    }


def weight_matrix_feature_ids() -> tuple[str, ...]:
    return tuple(V0_EVIDENCE_WEIGHTS)

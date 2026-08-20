"""Aggregation for social-navigation metric results."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from math import fsum

from .models import SOCIAL_NAVIGATION_AXIS_IDS, MetricStatus, MetricValue
from .scoring import default_axis_scoring_model, snap_score
from .weights import (
    V1_EVIDENCE_WEIGHTS,
    WEIGHT_MODEL_SOURCE,
    normalized_axis_weights,
)


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
    applied_caps: tuple[dict[str, object], ...] = ()
    reason: str | None = None

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
        status = _unscored_axis_status(omitted_statuses)
        return AxisScore(
            axis_id=axis_id,
            status=status,
            score=None,
            confidence=status.value,
            contributing_features=(),
            omitted_features=tuple(omitted),
            omitted_feature_statuses=omitted_statuses,
            model_metadata=_model_metadata(),
            reason=_unscored_axis_reason(status),
        )
    active_weight_total = fsum(weights[feature_id] for feature_id in scored)
    uncapped_score = fsum(
        scored[feature_id] * (weights[feature_id] / active_weight_total)
        for feature_id in scored
    )
    score, applied_caps = _apply_v1_axis_caps(
        axis_id,
        snap_score(uncapped_score),
        metric_values,
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
        applied_caps=applied_caps,
    )


def aggregate_axes(metric_values: Mapping[str, MetricValue]) -> dict[str, AxisScore]:
    return {
        axis_id: aggregate_axis(metric_values, axis_id)
        for axis_id in SOCIAL_NAVIGATION_AXIS_IDS
    }


def _model_metadata() -> dict[str, str]:
    return default_axis_scoring_model()


def _unscored_axis_status(omitted_statuses: Mapping[str, str]) -> MetricStatus:
    statuses = set(omitted_statuses.values())
    if statuses and statuses <= {MetricStatus.NOT_APPLICABLE.value}:
        return MetricStatus.NOT_APPLICABLE
    if MetricStatus.INVALID_INPUT.value in statuses:
        return MetricStatus.INVALID_INPUT
    return MetricStatus.INSUFFICIENT_EVIDENCE


def _unscored_axis_reason(status: MetricStatus) -> str:
    if status == MetricStatus.NOT_APPLICABLE:
        return "all weighted features were not applicable"
    if status == MetricStatus.INVALID_INPUT:
        return "all weighted features were omitted and at least one had invalid input"
    return "no weighted features had enough evidence to score"


def weight_matrix_feature_ids() -> tuple[str, ...]:
    return tuple(V1_EVIDENCE_WEIGHTS)


def _apply_v1_axis_caps(
    axis_id: str,
    score: float,
    metric_values: Mapping[str, MetricValue],
) -> tuple[float, tuple[dict[str, object], ...]]:
    caps = _v1_axis_caps(axis_id, metric_values)
    if not caps:
        return score, ()
    cap_value = min(float(cap["cap"]) for cap in caps)
    capped_score = min(score, cap_value)
    if capped_score == score:
        return score, ()
    return capped_score, tuple(caps)


def _v1_axis_caps(
    axis_id: str,
    metric_values: Mapping[str, MetricValue],
) -> list[dict[str, object]]:
    if axis_id == "perceived_dexterity":
        task_success = metric_values.get("task_success_rate")
        if task_success is not None and task_success.scored and task_success.normalized_score == 0.0:
            return [
                {
                    "kind": "v1_task_failure_cap",
                    "cap": 0.35,
                    "metric_id": "task_success_rate",
                    "source": WEIGHT_MODEL_SOURCE,
                }
            ]
        return []

    if axis_id != "perceived_safety":
        return []

    caps: list[dict[str, object]] = []
    stability = metric_values.get("stability")
    if stability is not None and stability.scored:
        raw = stability.raw_inputs_summary
        event_count = int(raw.get("collisions", 0)) + int(raw.get("instability_events", 0)) + int(
            raw.get("invalid_actions", 0)
        )
        if event_count > 0:
            caps.append(
                {
                    "kind": "v1_physical_instability_cap",
                    "cap": 0.20,
                    "metric_id": "stability",
                    "event_count": event_count,
                    "source": WEIGHT_MODEL_SOURCE,
                }
            )

    min_distance = metric_values.get("min_human_robot_distance")
    if min_distance is not None and min_distance.scored and min_distance.normalized_score == 0.0:
        caps.append(
            {
                "kind": "v1_hard_distance_violation_cap",
                "cap": 0.25,
                "metric_id": "min_human_robot_distance",
                "source": WEIGHT_MODEL_SOURCE,
            }
        )

    proxemic = metric_values.get("proxemic_intrusion_dose")
    speed = metric_values.get("speed_near_humans_p95")
    if (
        proxemic is not None
        and speed is not None
        and proxemic.scored
        and speed.scored
        and proxemic.normalized_score == 0.0
        and speed.normalized_score == 0.0
    ):
        caps.append(
            {
                "kind": "v1_high_risk_close_pass_cap",
                "cap": 0.35,
                "metric_id": "proxemic_intrusion_dose+speed_near_humans_p95",
                "source": WEIGHT_MODEL_SOURCE,
            }
        )
    return caps

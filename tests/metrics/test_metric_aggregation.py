from __future__ import annotations

import math

from asimovbm.metrics import SOCIAL_NAVIGATION_METRIC_IDS, MetricStatus, MetricValue
from asimovbm.metrics.aggregation import aggregate_axes


def _score(metric_id: str, value: float) -> MetricValue:
    return MetricValue(
        metric_id=metric_id,
        status=MetricStatus.COMPUTED,
        raw_value=value,
        normalized_score=value,
        confidence="sufficient",
    )


def test_aggregation_produces_four_axis_scores_from_scored_features() -> None:
    metrics = {metric_id: _score(metric_id, 1.0) for metric_id in SOCIAL_NAVIGATION_METRIC_IDS}

    axes = aggregate_axes(metrics)

    assert set(axes) == {
        "perceived_dexterity",
        "perceived_safety",
        "perceived_social_awareness",
        "impression",
    }
    assert {axis.score for axis in axes.values()} == {1.0}
    assert {axis.status for axis in axes.values()} == {MetricStatus.COMPUTED}


def test_not_applicable_features_are_omitted_and_remaining_weights_renormalized() -> None:
    metrics = {
        "task_success_rate": _score("task_success_rate", 1.0),
        "task_completion_time": MetricValue(
            metric_id="task_completion_time",
            status=MetricStatus.NOT_APPLICABLE,
            confidence="not_applicable",
        ),
        "hesitation": _score("hesitation", 0.0),
    }

    axes = aggregate_axes(metrics)

    dexterity = axes["perceived_dexterity"]
    assert dexterity.status == MetricStatus.COMPUTED
    assert math.isclose(dexterity.score or 0.0, 3.0 / 5.0)
    assert dexterity.confidence == "partial"
    assert "task_completion_time" in dexterity.omitted_features
    assert dexterity.omitted_feature_statuses["task_completion_time"] == "not_applicable"


def test_v1_task_failure_caps_dexterity_macro() -> None:
    metrics = {metric_id: _score(metric_id, 1.0) for metric_id in SOCIAL_NAVIGATION_METRIC_IDS}
    metrics["task_success_rate"] = _score("task_success_rate", 0.0)

    axes = aggregate_axes(metrics)

    dexterity = axes["perceived_dexterity"]
    assert dexterity.score == 0.35
    assert dexterity.applied_caps[0]["kind"] == "v1_task_failure_cap"


def test_v1_physical_instability_caps_safety_macro() -> None:
    metrics = {metric_id: _score(metric_id, 1.0) for metric_id in SOCIAL_NAVIGATION_METRIC_IDS}
    metrics["stability"] = MetricValue(
        metric_id="stability",
        status=MetricStatus.COMPUTED,
        raw_value=0.66,
        normalized_score=0.66,
        confidence="sufficient",
        raw_inputs_summary={"collisions": 1, "instability_events": 0, "invalid_actions": 0},
    )

    axes = aggregate_axes(metrics)

    safety = axes["perceived_safety"]
    assert safety.score == 0.2
    assert safety.applied_caps[0]["kind"] == "v1_physical_instability_cap"


def test_v1_hard_distance_violation_caps_safety_macro() -> None:
    metrics = {metric_id: _score(metric_id, 1.0) for metric_id in SOCIAL_NAVIGATION_METRIC_IDS}
    metrics["min_human_robot_distance"] = _score("min_human_robot_distance", 0.0)

    axes = aggregate_axes(metrics)

    safety = axes["perceived_safety"]
    assert safety.score == 0.25
    assert safety.applied_caps[0]["kind"] == "v1_hard_distance_violation_cap"


def test_v1_high_risk_close_pass_caps_safety_macro() -> None:
    metrics = {metric_id: _score(metric_id, 1.0) for metric_id in SOCIAL_NAVIGATION_METRIC_IDS}
    metrics["proxemic_intrusion_dose"] = _score("proxemic_intrusion_dose", 0.0)
    metrics["speed_near_humans_p95"] = _score("speed_near_humans_p95", 0.0)

    axes = aggregate_axes(metrics)

    safety = axes["perceived_safety"]
    assert safety.score == 0.35
    assert safety.applied_caps[0]["kind"] == "v1_high_risk_close_pass_cap"


def test_axis_without_scored_features_distinguishes_missing_evidence() -> None:
    axes = aggregate_axes({})

    assert axes["perceived_safety"].status == MetricStatus.INSUFFICIENT_EVIDENCE
    assert axes["perceived_safety"].score is None
    assert "missing" in set(axes["perceived_safety"].omitted_feature_statuses.values())

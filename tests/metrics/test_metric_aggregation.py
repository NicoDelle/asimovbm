from __future__ import annotations

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
        "task_success_rate": _score("task_success_rate", 0.0),
        "task_completion_time": MetricValue(
            metric_id="task_completion_time",
            status=MetricStatus.NOT_APPLICABLE,
            confidence="not_applicable",
        ),
    }

    axes = aggregate_axes(metrics)

    dexterity = axes["perceived_dexterity"]
    assert dexterity.status == MetricStatus.COMPUTED
    assert dexterity.score == 0.0
    assert dexterity.confidence == "partial"
    assert "task_completion_time" in dexterity.omitted_features
    assert dexterity.omitted_feature_statuses["task_completion_time"] == "not_applicable"


def test_axis_without_scored_features_is_not_applicable() -> None:
    axes = aggregate_axes({})

    assert axes["perceived_safety"].status == MetricStatus.NOT_APPLICABLE
    assert axes["perceived_safety"].score is None
    assert "missing" in set(axes["perceived_safety"].omitted_feature_statuses.values())

from __future__ import annotations

from asimovbm.metrics import (
    SOCIAL_NAVIGATION_AXIS_IDS,
    SOCIAL_NAVIGATION_METRIC_IDS,
    MetricStatus,
    MetricValue,
    aggregate_axes,
)
from asimovbm.reports import (
    JsonReportInput,
    build_behavioral_metric_block,
    build_json_report,
)


def _score(metric_id: str, value: float) -> MetricValue:
    return MetricValue(
        metric_id=metric_id,
        status=MetricStatus.COMPUTED,
        raw_value=value,
        normalized_score=value,
        confidence="sufficient",
    )


def test_behavioral_report_block_exposes_axes_and_all_metric_features() -> None:
    metrics = {
        metric_id: _score(metric_id, 0.75)
        for metric_id in SOCIAL_NAVIGATION_METRIC_IDS
    }

    block = build_behavioral_metric_block(aggregate_axes(metrics), metrics)
    report = build_json_report(
        JsonReportInput(
            run_id="run-1",
            maturity="local_validation",
            behavioral_metrics=block,
        )
    )

    behavioral = report["behavioral_metrics"]
    assert behavioral["status"] == "scored"
    assert tuple(behavioral["axes"]) == SOCIAL_NAVIGATION_AXIS_IDS
    assert tuple(behavioral["features"]) == SOCIAL_NAVIGATION_METRIC_IDS
    assert len(behavioral["macro_indicators"]) == 4
    assert len(behavioral["sub_indicators"]) == 16
    assert behavioral["features"]["task_success_rate"]["normalized_score"] == 0.75
    assert behavioral["axes"]["perceived_safety"]["status"] == "computed"

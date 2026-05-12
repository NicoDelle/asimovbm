from __future__ import annotations

from asimovbm.metrics import MetricStatus, MetricValue


def test_computed_metric_value_carries_raw_normalized_and_evidence() -> None:
    value = MetricValue(
        metric_id="task_success_rate",
        status=MetricStatus.COMPUTED,
        raw_value=0.75,
        normalized_score=0.75,
        confidence="sufficient",
        units="ratio",
        raw_inputs_summary={"valid_episodes": 4},
    )

    assert value.scored
    assert value.raw_value == 0.75
    assert value.normalized_score == 0.75
    assert value.raw_inputs_summary == {"valid_episodes": 4}


def test_not_applicable_metric_value_is_not_a_zero_score() -> None:
    value = MetricValue(
        metric_id="speed_near_humans_p95",
        status=MetricStatus.NOT_APPLICABLE,
        confidence="not_applicable",
        reason="robot never entered the near-human zone",
    )

    assert not value.scored
    assert value.raw_value is None
    assert value.normalized_score is None
    assert value.confidence == "not_applicable"


def test_insufficient_evidence_metric_value_preserves_reason() -> None:
    value = MetricValue(
        metric_id="sparc",
        status=MetricStatus.INSUFFICIENT_EVIDENCE,
        confidence="insufficient",
        reason="requires at least three samples",
    )

    assert not value.scored
    assert value.reason == "requires at least three samples"

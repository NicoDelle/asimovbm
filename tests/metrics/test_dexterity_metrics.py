from __future__ import annotations

from asimovbm.metrics import MetricStatus
from asimovbm.metrics.comfort_aware_path_efficiency import (
    PathEfficiencyAttempt,
)
from asimovbm.metrics.comfort_aware_path_efficiency import (
    compute as compute_path_efficiency,
)
from asimovbm.metrics.completion_time import compute as compute_completion_time
from asimovbm.metrics.hesitation import compute as compute_hesitation
from asimovbm.metrics.task_success_rate import (
    TaskSuccessAttempt,
)
from asimovbm.metrics.task_success_rate import (
    compute as compute_task_success,
)


def test_task_success_requires_acknowledgement_stop_band_and_timeout() -> None:
    result = compute_task_success(
        attempts=[
            TaskSuccessAttempt(True, 1.0, 20.0, "success"),
            TaskSuccessAttempt(True, 2.0, 20.0, "success"),
            TaskSuccessAttempt(False, 1.0, 20.0, "success"),
        ]
    )

    assert result.status == MetricStatus.COMPUTED
    assert result.raw_value == 1 / 3
    assert result.normalized_score == 1 / 3


def test_completion_time_is_not_applicable_without_successes() -> None:
    result = compute_completion_time(successful_durations=[])

    assert result.status == MetricStatus.NOT_APPLICABLE
    assert result.normalized_score is None


def test_comfort_aware_path_efficiency_guards_high_density_intrusion() -> None:
    result = compute_path_efficiency(
        attempts=[
            PathEfficiencyAttempt(True, actual_outside_comfort=0.05, actual_total=2.0, optimal_outside_comfort=1.0),
            PathEfficiencyAttempt(True, actual_outside_comfort=1.2, actual_total=2.0, optimal_outside_comfort=1.0),
            PathEfficiencyAttempt(True, actual_outside_comfort=1.0, actual_total=2.0, optimal_outside_comfort=1.0),
        ]
    )

    assert result.status == MetricStatus.COMPUTED
    assert result.raw_value < 1.0


def test_comfort_aware_path_efficiency_requires_optimal_length() -> None:
    result = compute_path_efficiency(
        attempts=[
            PathEfficiencyAttempt(True, actual_outside_comfort=1.0, actual_total=2.0, optimal_outside_comfort=None)
        ]
    )

    assert result.status == MetricStatus.INSUFFICIENT_EVIDENCE


def test_hesitation_ignores_yielding_and_post_success_settling() -> None:
    times = [0.0, 0.5, 1.0, 1.5, 2.0]
    result = compute_hesitation(
        times=times,
        speeds=[0.0, 0.0, 0.0, 0.0, 0.0],
        headings=[0.0] * len(times),
        target_bearings=[0.0] * len(times),
        yielding_mask=[True, True, False, False, False],
        goal_reached_mask=[False, False, True, True, True],
    )

    assert result.status == MetricStatus.COMPUTED
    assert result.raw_value == 0.0


def test_hesitation_counts_reversal_with_displacement_gate() -> None:
    times = [0.0, 0.5, 1.0, 1.5]
    result = compute_hesitation(
        times=times,
        speeds=[0.2, 0.2, 0.2, 0.2],
        headings=[3.14, 3.14, 3.14, 3.14],
        target_bearings=[0.0, 0.0, 0.0, 0.0],
    )

    assert result.status == MetricStatus.COMPUTED
    assert result.raw_inputs_summary["reversal_epochs"] == 1

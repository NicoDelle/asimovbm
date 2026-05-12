from __future__ import annotations

from asimovbm.metrics import MetricStatus
from asimovbm.metrics.sparc import compute


def test_smooth_signal_scores_better_than_jerky_signal() -> None:
    times = [index * 0.1 for index in range(20)]
    smooth = [1.0 for _ in times]
    jerky = [0.0 if index % 2 == 0 else 2.0 for index, _ in enumerate(times)]

    smooth_result = compute(samples=smooth, times=times)
    jerky_result = compute(samples=jerky, times=times)

    assert smooth_result.status == MetricStatus.COMPUTED
    assert jerky_result.status == MetricStatus.COMPUTED
    assert smooth_result.normalized_score > jerky_result.normalized_score


def test_non_uniform_sampling_is_insufficient_evidence() -> None:
    result = compute(samples=[0.0, 1.0, 0.0, 1.0], times=[0.0, 0.1, 0.25, 0.3])

    assert result.status == MetricStatus.INSUFFICIENT_EVIDENCE
    assert "uniformly sampled" in result.reason

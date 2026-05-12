from __future__ import annotations

import math

from asimovbm.metrics import MetricStatus
from asimovbm.metrics.behavioral_naturalness import compute as compute_naturalness
from asimovbm.metrics.heading_jerk import compute as compute_heading_jerk
from asimovbm.metrics.legibility import compute as compute_legibility
from asimovbm.metrics.stability import compute as compute_stability


def test_heading_jerk_scores_smooth_yaw_better_than_abrupt_swerves() -> None:
    times = [index * 0.1 for index in range(20)]
    smooth = [0.2 for _ in times]
    jerky = [0.0 if index % 2 == 0 else 2.0 for index, _ in enumerate(times)]

    assert compute_heading_jerk(yaw_rates=smooth, times=times).normalized_score > compute_heading_jerk(
        yaw_rates=jerky,
        times=times,
    ).normalized_score


def test_stability_reaches_bad_bound_after_three_events() -> None:
    result = compute_stability(instability_events=1, collisions=1, invalid_actions=1)

    assert result.status == MetricStatus.COMPUTED
    assert result.normalized_score == 0.0


def test_legibility_rewards_early_commitment_with_fractional_coverage() -> None:
    result = compute_legibility(
        times=[0.0, 0.5, 1.0, 1.5, 2.0],
        heading_errors=[1.0, 0.1, 0.1, 0.4, 0.1],
    )

    assert result.status == MetricStatus.COMPUTED
    assert 0.0 < result.raw_value < 1.0


def test_legibility_scores_zero_when_no_commit_window_exists() -> None:
    result = compute_legibility(
        times=[0.0, 0.5, 1.0, 1.5],
        heading_errors=[1.0, 1.0, 1.0, 1.0],
    )

    assert result.raw_value == 0.0


def test_legged_naturalness_scores_regular_sinusoid_high() -> None:
    times = [index * 0.05 for index in range(80)]
    signal = [math.sin(2.0 * math.pi * time) for time in times]

    result = compute_naturalness(
        morphology="legged",
        irreg_max=0.4,
        joint_signal=signal,
        times=times,
    )

    assert result.status == MetricStatus.COMPUTED
    assert result.normalized_score > 0.9


def test_wheeled_naturalness_uses_lateral_velocity_ratio() -> None:
    result = compute_naturalness(
        morphology="wheeled",
        irreg_max=0.4,
        lateral_velocities=[0.01, -0.01, 0.0],
        forward_velocities=[1.0, 1.0, 1.0],
    )

    assert result.status == MetricStatus.COMPUTED
    assert result.normalized_score > 0.9


def test_naturalness_not_applicable_for_undeclared_morphology() -> None:
    result = compute_naturalness(morphology=None, irreg_max=None)

    assert result.status == MetricStatus.NOT_APPLICABLE

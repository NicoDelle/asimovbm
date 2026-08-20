from __future__ import annotations

from asimovbm.metrics import MetricStatus
from asimovbm.metrics.min_human_robot_distance import compute as compute_min_distance
from asimovbm.metrics.proxemic_intrusion_dose import compute as compute_intrusion
from asimovbm.metrics.speed_near_humans_p95 import compute as compute_speed_near


def test_minimum_distance_reaches_bad_bound_at_hard_floor() -> None:
    result = compute_min_distance(
        robot_positions=[(0.0, 0.0)],
        human_positions=[[(0.45, 0.0)]],
    )

    assert result.status == MetricStatus.COMPUTED
    assert result.normalized_score == 0.0


def test_proxemic_intrusion_integrates_depth_over_time() -> None:
    result = compute_intrusion(
        times=[0.0, 1.0, 2.0],
        robot_positions=[(0.0, 0.0), (0.0, 0.0), (0.0, 0.0)],
        human_positions=[[(1.2, 0.0)], [(0.7, 0.0)], [(1.2, 0.0)]],
        bystanders_present=False,
    )

    assert result.status == MetricStatus.COMPUTED
    assert result.raw_value == 0.5
    assert result.raw_inputs_summary["bystander_intrusion_applicable"] is False


def test_speed_near_humans_uses_p95_not_mean() -> None:
    result = compute_speed_near(
        speeds=[0.1, 0.1, 0.1, 1.0],
        min_human_distances=[1.0, 1.0, 1.0, 1.0],
    )

    assert result.status == MetricStatus.COMPUTED
    assert result.raw_value > 0.8


def test_speed_near_humans_is_not_applicable_when_never_near() -> None:
    result = compute_speed_near(
        speeds=[1.0, 1.0],
        min_human_distances=[3.0, 3.5],
    )

    assert result.status == MetricStatus.NOT_APPLICABLE

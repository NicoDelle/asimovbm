"""Extract metric inputs from local traces and invoke real metric functions."""

from __future__ import annotations

from math import atan2, hypot
from typing import Any

from asimovbm.metrics import (
    SOCIAL_NAVIGATION_METRIC_IDS,
    MetricStatus,
    MetricValue,
    aggregate_axes,
)
from asimovbm.metrics.comfort_aware_path_efficiency import PathEfficiencyAttempt
from asimovbm.metrics.comfort_aware_path_efficiency import compute as compute_path_efficiency
from asimovbm.metrics.completion_time import compute as compute_completion_time
from asimovbm.metrics.heading_jerk import compute as compute_heading_jerk
from asimovbm.metrics.hesitation import compute as compute_hesitation
from asimovbm.metrics.legibility import compute as compute_legibility
from asimovbm.metrics.sparc import compute as compute_sparc
from asimovbm.metrics.stability import compute as compute_stability
from asimovbm.metrics.task_success_rate import TaskSuccessAttempt
from asimovbm.metrics.task_success_rate import compute as compute_task_success
from asimovbm.reports import build_behavioral_metric_block

from .traces import LocalEpisodeTrace


def compute_metrics_for_trace(trace: LocalEpisodeTrace) -> dict[str, MetricValue]:
    if not trace.technical_valid:
        return {
            metric_id: MetricValue(
                metric_id=metric_id,
                status=MetricStatus.INSUFFICIENT_EVIDENCE,
                confidence="insufficient",
                reason=f"technical failure: {trace.terminal_status}",
            )
            for metric_id in SOCIAL_NAVIGATION_METRIC_IDS
        }

    positions = [(step.robot_pose[0], step.robot_pose[1]) for step in trace.steps]
    times = [step.time_s for step in trace.steps]
    speeds = [hypot(step.robot_velocity[0], step.robot_velocity[1]) for step in trace.steps]
    yaw_rates = [step.robot_velocity[2] for step in trace.steps]
    heading_errors = _heading_errors_to_goal(trace)
    path_length = _path_length(positions)
    optimal_length = _straight_line_length(trace)
    success = trace.terminal_status == "success"
    final_distance = trace.final_distance_to_goal
    completion_time = trace.duration_s if success else None

    values: dict[str, MetricValue] = {
        "task_success_rate": compute_task_success(
            attempts=[
                TaskSuccessAttempt(
                    acknowledged=True,
                    final_distance=final_distance,
                    stop_time=completion_time,
                    terminal_state=trace.terminal_status,
                )
            ]
        ),
        "task_completion_time": compute_completion_time(
            successful_durations=[trace.duration_s] if success else []
        ),
        "comfort_aware_path_efficiency": compute_path_efficiency(
            attempts=[
                PathEfficiencyAttempt(
                    successful=success,
                    actual_outside_comfort=path_length,
                    actual_total=path_length,
                    optimal_outside_comfort=optimal_length,
                    used_unconstrained_fallback=True,
                )
            ]
        ),
        "hesitation": compute_hesitation(
            times=times,
            speeds=speeds,
            headings=[step.robot_pose[2] for step in trace.steps],
            target_bearings=_target_bearings(trace),
        ),
        "sparc": compute_sparc(samples=speeds, times=times),
        "heading_jerk": compute_heading_jerk(yaw_rates=yaw_rates, times=times),
        "stability": compute_stability(collisions=trace.collision_count),
        "legibility": compute_legibility(times=times, heading_errors=heading_errors),
    }
    for metric_id in SOCIAL_NAVIGATION_METRIC_IDS:
        values.setdefault(metric_id, _not_applicable(metric_id, "no human/social-cue entities in g1_slam six-episode trace"))
    return values


def build_trace_metric_report(trace: LocalEpisodeTrace) -> dict[str, Any]:
    values = compute_metrics_for_trace(trace)
    axes = aggregate_axes(values)
    return {
        "episode_id": trace.episode_id,
        "iteration": trace.iteration,
        "technical_valid": trace.technical_valid,
        "terminal_status": trace.terminal_status,
        "metrics": {metric_id: _metric_to_dict(value) for metric_id, value in values.items()},
        "behavioral_metrics": build_behavioral_metric_block(axes, values),
    }


def _not_applicable(metric_id: str, reason: str) -> MetricValue:
    return MetricValue(
        metric_id=metric_id,
        status=MetricStatus.NOT_APPLICABLE,
        confidence="not_applicable",
        reason=reason,
    )


def _metric_to_dict(value: MetricValue) -> dict[str, Any]:
    from dataclasses import asdict

    payload = asdict(value)
    payload["status"] = value.status.value
    return payload


def _path_length(positions: list[tuple[float, float]]) -> float:
    if len(positions) < 2:
        return 0.0
    return sum(
        hypot(b[0] - a[0], b[1] - a[1])
        for a, b in zip(positions, positions[1:], strict=False)
    )


def _straight_line_length(trace: LocalEpisodeTrace) -> float:
    start = trace.metadata.get("start")
    goal = trace.metadata.get("goal")
    if not isinstance(start, tuple) or not isinstance(goal, tuple):
        positions = [(step.robot_pose[0], step.robot_pose[1]) for step in trace.steps]
        if len(positions) < 2:
            return 0.0
        start = positions[0]
        goal = positions[-1]
    return hypot(goal[0] - start[0], goal[1] - start[1])


def _target_bearings(trace: LocalEpisodeTrace) -> list[float]:
    goal = trace.metadata.get("goal")
    if not isinstance(goal, tuple):
        if not trace.steps:
            return []
        last = trace.steps[-1].robot_pose
        goal = (last[0], last[1])
    return [atan2(goal[1] - step.robot_pose[1], goal[0] - step.robot_pose[0]) for step in trace.steps]


def _heading_errors_to_goal(trace: LocalEpisodeTrace) -> list[float]:
    return [
        abs(_wrap_angle(bearing - step.robot_pose[2]))
        for step, bearing in zip(trace.steps, _target_bearings(trace), strict=False)
    ]


def _wrap_angle(angle: float) -> float:
    while angle > 3.141592653589793:
        angle -= 2.0 * 3.141592653589793
    while angle < -3.141592653589793:
        angle += 2.0 * 3.141592653589793
    return angle

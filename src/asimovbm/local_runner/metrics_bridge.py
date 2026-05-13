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
from asimovbm.metrics.acknowledgement_clarity import AcknowledgementAttempt
from asimovbm.metrics.acknowledgement_clarity import compute as compute_acknowledgement
from asimovbm.metrics.behavioral_naturalness import compute as compute_naturalness
from asimovbm.metrics.bystander_ack import compute as compute_bystander_ack
from asimovbm.metrics.comfort_aware_path_efficiency import PathEfficiencyAttempt
from asimovbm.metrics.comfort_aware_path_efficiency import compute as compute_path_efficiency
from asimovbm.metrics.completion_time import compute as compute_completion_time
from asimovbm.metrics.heading_jerk import compute as compute_heading_jerk
from asimovbm.metrics.hesitation import compute as compute_hesitation
from asimovbm.metrics.human_aware_approach import HumanAwareApproachAttempt
from asimovbm.metrics.human_aware_approach import compute as compute_human_aware_approach
from asimovbm.metrics.legibility import compute as compute_legibility
from asimovbm.metrics.min_human_robot_distance import compute as compute_min_distance
from asimovbm.metrics.proxemic_intrusion_dose import compute as compute_proxemic_dose
from asimovbm.metrics.sparc import compute as compute_sparc
from asimovbm.metrics.speed_near_humans_p95 import compute as compute_speed_near_humans
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
    human_positions = _human_positions_by_step(trace)
    has_human_telemetry = any(human_positions)
    min_human_distances = _min_human_distances(positions, human_positions)
    heading_errors = _heading_errors_to_goal(trace)
    path_length = _path_length(positions)
    optimal_length = _straight_line_length(trace)
    success = trace.terminal_status == "success"
    final_distance = _task_success_final_distance(trace, success)
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
        "min_human_robot_distance": compute_min_distance(
            robot_positions=positions,
            human_positions=human_positions,
        )
        if has_human_telemetry
        else _insufficient("min_human_robot_distance", "trace does not include human poses"),
        "proxemic_intrusion_dose": compute_proxemic_dose(
            times=times,
            robot_positions=positions,
            human_positions=human_positions,
            bystanders_present=_has_bystanders(trace),
        )
        if has_human_telemetry
        else _insufficient("proxemic_intrusion_dose", "trace does not include human poses"),
        "speed_near_humans_p95": compute_speed_near_humans(
            speeds=speeds,
            min_human_distances=min_human_distances,
        )
        if has_human_telemetry
        else _insufficient("speed_near_humans_p95", "trace does not include human poses"),
        "gesture_response_success": _gesture_response(trace),
        "acknowledgement_clarity": compute_acknowledgement(
            attempts=_acknowledgement_attempts(trace, heading_errors)
        ),
        "human_aware_approach": _human_aware_approach(trace, positions, human_positions),
        "bystander_ack": compute_bystander_ack(passes=()),
        "sparc": compute_sparc(samples=speeds, times=times),
        "heading_jerk": compute_heading_jerk(yaw_rates=yaw_rates, times=times),
        "stability": compute_stability(collisions=trace.collision_count),
        "legibility": compute_legibility(times=times, heading_errors=heading_errors),
        "behavioral_naturalness": compute_naturalness(
            morphology=_morphology(trace),
            irreg_max=1.0,
            lateral_velocities=[step.robot_velocity[1] for step in trace.steps],
            forward_velocities=[step.robot_velocity[0] for step in trace.steps],
        ),
    }
    for metric_id in SOCIAL_NAVIGATION_METRIC_IDS:
        values.setdefault(metric_id, _insufficient(metric_id, "metric bridge did not derive required trace inputs"))
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


def _insufficient(metric_id: str, reason: str) -> MetricValue:
    return MetricValue(
        metric_id=metric_id,
        status=MetricStatus.INSUFFICIENT_EVIDENCE,
        confidence="insufficient",
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


def _task_success_final_distance(trace: LocalEpisodeTrace, success: bool) -> float | None:
    if not success:
        return trace.final_distance_to_goal
    stop_band_distance = trace.metadata.get("target_stop_distance")
    if isinstance(stop_band_distance, int | float):
        return float(stop_band_distance)
    return 1.0


def _human_positions_by_step(trace: LocalEpisodeTrace) -> list[list[tuple[float, float]]]:
    return [_human_positions(step.static_entities + step.dynamic_entities) for step in trace.steps]


def _human_positions(entities) -> list[tuple[float, float]]:
    positions: list[tuple[float, float]] = []
    for entity in entities:
        if entity.get("type") not in {"human", "target", "bystander"}:
            continue
        pose = entity.get("pose")
        if isinstance(pose, (tuple, list)) and len(pose) >= 2:
            positions.append((float(pose[0]), float(pose[1])))
    return positions


def _min_human_distances(
    robot_positions: list[tuple[float, float]],
    human_positions: list[list[tuple[float, float]]],
) -> list[float]:
    distances: list[float] = []
    for robot, humans in zip(robot_positions, human_positions, strict=True):
        if not humans:
            distances.append(float("inf"))
            continue
        distances.append(min(hypot(robot[0] - human[0], robot[1] - human[1]) for human in humans))
    return distances


def _has_bystanders(trace: LocalEpisodeTrace) -> bool:
    for step in trace.steps:
        for entity in step.static_entities + step.dynamic_entities:
            if entity.get("type") == "bystander" or entity.get("role") == "bystander":
                return True
    return False


def _gesture_response(trace: LocalEpisodeTrace) -> MetricValue:
    from asimovbm.metrics.gesture_response_success import GestureResponseAttempt
    from asimovbm.metrics.gesture_response_success import compute as compute_gesture

    attempts = []
    for step in trace.steps:
        for cue in step.social_cues:
            if cue.get("type") == "come_here":
                attempts.append(
                    GestureResponseAttempt(
                        has_event=True,
                        response_time=cue.get("response_time"),
                        moved_toward_target=bool(cue.get("moved_toward_target", False)),
                        moved_toward_non_target_first=bool(cue.get("moved_toward_non_target_first", False)),
                    )
                )
    return compute_gesture(attempts=attempts)


def _acknowledgement_attempts(
    trace: LocalEpisodeTrace,
    heading_errors: list[float],
) -> list[AcknowledgementAttempt]:
    if not trace.steps or not heading_errors:
        return []
    return [
        AcknowledgementAttempt(
            min_bearing_error=min(heading_errors),
            time_to_cone=_first_time_inside_heading_cone(trace, heading_errors),
            approach_start_time=trace.steps[0].time_s,
            has_forward_axis=True,
        )
    ]


def _first_time_inside_heading_cone(trace: LocalEpisodeTrace, heading_errors: list[float]) -> float | None:
    for step, error in zip(trace.steps, heading_errors, strict=False):
        if error <= 0.35:
            return step.time_s
    return None


def _human_aware_approach(
    trace: LocalEpisodeTrace,
    positions: list[tuple[float, float]],
    human_positions: list[list[tuple[float, float]]],
) -> MetricValue:
    first_humans = next((humans for humans in human_positions if humans), None)
    if not first_humans or not positions:
        return _insufficient("human_aware_approach", "trace does not include human poses")
    target = first_humans[0]
    start_distance = hypot(positions[0][0] - target[0], positions[0][1] - target[1])
    final_distance = hypot(positions[-1][0] - target[0], positions[-1][1] - target[1])
    return compute_human_aware_approach(
        attempts=[
            HumanAwareApproachAttempt(
                start_distance_to_target=start_distance,
                final_distance_to_target=final_distance,
                used_closest_approach_fallback=True,
            )
        ]
    )


def _morphology(trace: LocalEpisodeTrace) -> str:
    if "go2" in trace.robot_selector:
        return "quadruped"
    if "g1" in trace.robot_selector:
        return "humanoid"
    return "mobile_base"


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

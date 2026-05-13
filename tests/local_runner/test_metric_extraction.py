from __future__ import annotations

from asimovbm.local_runner.metrics_bridge import compute_metrics_for_trace
from asimovbm.local_runner.traces import LocalEpisodeTrace, LocalStepTrace
from asimovbm.metrics import MetricStatus


def test_metric_bridge_computes_core_metrics_and_marks_missing_human_telemetry_insufficient() -> None:
    trace = LocalEpisodeTrace(
        episode_id="g1_approach_user",
        iteration=0,
        tier_id="g1_slam_canonical",
        technical_valid=True,
        terminal_status="success",
        steps=tuple(
            LocalStepTrace(
                step_id=index,
                time_s=float(index + 1),
                dt_s=1.0,
                robot_pose=(float(index) * 0.3, 0.0, 0.0),
                robot_velocity=(0.3, 0.0, 0.0),
                action=(0.3, 0.0),
                distance_to_goal=max(0.0, 1.0 - index * 0.3),
            )
            for index in range(5)
        ),
        config_checksum_sha256="abc123",
        config_path="g1_slam/config/episodes/g1_approach_user.json",
        robot_selector="official_g1",
        canonical_backend_id="g1_robojudo",
        execution_backend_id="g1_slam_reference_trace_v1",
        viewer_mode="visible",
        metadata={"start": (0.0, 0.0), "goal": (1.2, 0.0)},
    )

    metrics = compute_metrics_for_trace(trace)

    assert metrics["task_success_rate"].status == MetricStatus.COMPUTED
    assert metrics["task_completion_time"].status == MetricStatus.COMPUTED
    assert metrics["comfort_aware_path_efficiency"].status == MetricStatus.COMPUTED
    assert metrics["min_human_robot_distance"].status == MetricStatus.INSUFFICIENT_EVIDENCE
    assert metrics["proxemic_intrusion_dose"].status == MetricStatus.INSUFFICIENT_EVIDENCE
    assert metrics["speed_near_humans_p95"].status == MetricStatus.INSUFFICIENT_EVIDENCE

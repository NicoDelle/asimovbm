from __future__ import annotations

from asimovbm.local_runner.metrics_bridge import compute_metrics_for_trace
from asimovbm.local_runner.traces import LocalEpisodeTrace, LocalStepTrace
from asimovbm.metrics import MetricStatus


def test_metric_bridge_computes_core_metrics_and_marks_human_metrics_not_applicable() -> None:
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
    assert metrics["min_human_robot_distance"].status == MetricStatus.NOT_APPLICABLE


def test_metric_bridge_computes_safety_metrics_from_human_entities() -> None:
    trace = LocalEpisodeTrace(
        episode_id="g1_lateral_static_dynamic_obstacles",
        iteration=0,
        tier_id="g1_slam_canonical",
        technical_valid=True,
        terminal_status="success",
        steps=(
            LocalStepTrace(
                step_id=0,
                time_s=0.0,
                dt_s=1.0,
                robot_pose=(0.0, 0.0, 0.0),
                robot_velocity=(0.2, 0.0, 0.0),
                action=(0.2, 0.0),
                distance_to_goal=1.0,
                dynamic_entities=(
                    {
                        "id": "person_npc_0",
                        "type": "human",
                        "role": "bystander",
                        "pose": (2.0, 0.0, 0.0),
                        "radius": 0.28,
                    },
                ),
            ),
            LocalStepTrace(
                step_id=1,
                time_s=1.0,
                dt_s=1.0,
                robot_pose=(0.5, 0.0, 0.0),
                robot_velocity=(0.8, 0.0, 0.0),
                action=(0.8, 0.0),
                distance_to_goal=0.5,
                dynamic_entities=(
                    {
                        "id": "person_npc_0",
                        "type": "human",
                        "role": "bystander",
                        "pose": (1.5, 0.0, 0.0),
                        "radius": 0.28,
                    },
                ),
            ),
            LocalStepTrace(
                step_id=2,
                time_s=2.0,
                dt_s=1.0,
                robot_pose=(1.0, 0.0, 0.0),
                robot_velocity=(1.0, 0.0, 0.0),
                action=(1.0, 0.0),
                distance_to_goal=0.0,
                dynamic_entities=(
                    {
                        "id": "person_npc_0",
                        "type": "human",
                        "role": "bystander",
                        "pose": (1.8, 0.0, 0.0),
                        "radius": 0.28,
                    },
                ),
            ),
        ),
        config_checksum_sha256="abc123",
        config_path="g1_slam/config/episodes/g1_lateral_static_dynamic_obstacles.json",
        robot_selector="official_g1",
        canonical_backend_id="g1_robojudo",
        execution_backend_id="g1_slam_reference_trace_v1",
        viewer_mode="headless",
        measurement_proof_level="reference",
        metadata={"start": (0.0, 0.0), "goal": (1.0, 0.0)},
    )

    metrics = compute_metrics_for_trace(trace)

    assert metrics["min_human_robot_distance"].status == MetricStatus.COMPUTED
    assert metrics["min_human_robot_distance"].raw_value == 0.8
    assert metrics["proxemic_intrusion_dose"].status == MetricStatus.COMPUTED
    assert round(metrics["proxemic_intrusion_dose"].raw_value, 6) == 0.4
    assert metrics["speed_near_humans_p95"].status == MetricStatus.COMPUTED
    assert metrics["speed_near_humans_p95"].raw_inputs_summary["near_zone_samples"] == 2
    assert metrics["gesture_response_success"].status == MetricStatus.NOT_APPLICABLE


def test_metric_bridge_rejects_misaligned_human_streams() -> None:
    trace = LocalEpisodeTrace(
        episode_id="broken",
        iteration=0,
        tier_id="g1_slam_canonical",
        technical_valid=True,
        terminal_status="success",
        steps=(
            LocalStepTrace(
                step_id=0,
                time_s=0.0,
                dt_s=1.0,
                robot_pose=(0.0, 0.0, 0.0),
                robot_velocity=(0.2, 0.0, 0.0),
                action=(0.2, 0.0),
                distance_to_goal=1.0,
                dynamic_entities=({"id": "person_npc_0", "type": "human", "pose": (1.0, 0.0, 0.0)},),
            ),
            LocalStepTrace(
                step_id=1,
                time_s=1.0,
                dt_s=1.0,
                robot_pose=(0.5, 0.0, 0.0),
                robot_velocity=(0.2, 0.0, 0.0),
                action=(0.2, 0.0),
                distance_to_goal=0.5,
                dynamic_entities=({"id": "person_npc_0", "type": "human", "pose": (1.0,)},),
            ),
        ),
        config_checksum_sha256="abc123",
        config_path="broken.json",
        robot_selector="official_g1",
        canonical_backend_id="g1_robojudo",
        execution_backend_id="g1_slam_reference_trace_v1",
        viewer_mode="headless",
        measurement_proof_level="reference",
    )

    metrics = compute_metrics_for_trace(trace)

    assert metrics["min_human_robot_distance"].status == MetricStatus.INSUFFICIENT_EVIDENCE
    assert metrics["proxemic_intrusion_dose"].status == MetricStatus.INSUFFICIENT_EVIDENCE
    assert metrics["speed_near_humans_p95"].status == MetricStatus.INSUFFICIENT_EVIDENCE

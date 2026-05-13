from __future__ import annotations

from asimovbm.local_runner.traces import LocalEpisodeTrace, LocalStepTrace
from asimovbm.metrics import (
    SOCIAL_NAVIGATION_METRIC_IDS,
    default_metric_registry,
)


def test_default_metric_registry_exposes_all_social_navigation_metric_ids() -> None:
    registry = default_metric_registry()

    assert registry.metric_ids == SOCIAL_NAVIGATION_METRIC_IDS
    assert len(registry.metric_ids) == 16
    assert registry.metric_ids == (
        "task_success_rate",
        "task_completion_time",
        "comfort_aware_path_efficiency",
        "hesitation",
        "min_human_robot_distance",
        "proxemic_intrusion_dose",
        "speed_near_humans_p95",
        "gesture_response_success",
        "acknowledgement_clarity",
        "human_aware_approach",
        "bystander_ack",
        "sparc",
        "heading_jerk",
        "stability",
        "legibility",
        "behavioral_naturalness",
    )


def test_default_metric_registry_delegates_local_traces_to_metric_bridge() -> None:
    registry = default_metric_registry()
    trace = LocalEpisodeTrace(
        episode_id="registry-check",
        iteration=0,
        tier_id="g1_slam_canonical",
        technical_valid=True,
        terminal_status="success",
        steps=(
            LocalStepTrace(
                step_id=0,
                time_s=0.1,
                dt_s=0.1,
                robot_pose=(0.0, 0.0, 0.0),
                robot_velocity=(0.1, 0.0, 0.0),
                action=(0.1, 0.0),
                distance_to_goal=1.0,
            ),
            LocalStepTrace(
                step_id=1,
                time_s=0.2,
                dt_s=0.1,
                robot_pose=(0.1, 0.0, 0.0),
                robot_velocity=(0.1, 0.0, 0.0),
                action=(0.1, 0.0),
                distance_to_goal=0.2,
            ),
        ),
        config_checksum_sha256="abc",
        config_path="episode.json",
        robot_selector="kinematic",
        canonical_backend_id="g1_slam_kinematic",
        execution_backend_id="test",
        viewer_mode="headless",
    )

    values = registry.compute(trace)

    assert values["task_success_rate"].status == "computed"
    assert values["task_success_rate"].normalized_score == 1.0
    assert "trace_adapter" not in values["task_success_rate"].raw_inputs_summary

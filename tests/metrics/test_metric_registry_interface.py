from __future__ import annotations

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

"""V1 social-navigation feature-to-axis weights."""

from __future__ import annotations

from collections.abc import Mapping
from math import fsum

from .models import SOCIAL_NAVIGATION_AXIS_IDS, SOCIAL_NAVIGATION_METRIC_IDS

WEIGHT_MODEL_KIND = "manual_v1_evidence_weights"
WEIGHT_MODEL_VERSION = "v1"
WEIGHT_MODEL_SOURCE = "docs/metrics_research/hri_metric_weighting_artifact.md"

V1_EVIDENCE_WEIGHTS: dict[str, dict[str, float]] = {
    "task_success_rate": {
        "perceived_dexterity": 3,
        "perceived_safety": 1,
        "perceived_social_awareness": 0,
        "impression": 1,
    },
    "task_completion_time": {
        "perceived_dexterity": 1,
        "perceived_safety": 0,
        "perceived_social_awareness": 0,
        "impression": 0,
    },
    "comfort_aware_path_efficiency": {
        "perceived_dexterity": 1,
        "perceived_safety": 1,
        "perceived_social_awareness": 0.5,
        "impression": 0,
    },
    "hesitation": {
        "perceived_dexterity": 2,
        "perceived_safety": 1.5,
        "perceived_social_awareness": 0.5,
        "impression": 1,
    },
    "min_human_robot_distance": {
        "perceived_dexterity": 0,
        "perceived_safety": 3,
        "perceived_social_awareness": 2,
        "impression": 0.5,
    },
    "proxemic_intrusion_dose": {
        "perceived_dexterity": 0,
        "perceived_safety": 3,
        "perceived_social_awareness": 3,
        "impression": 2,
    },
    "speed_near_humans_p95": {
        "perceived_dexterity": 1,
        "perceived_safety": 3,
        "perceived_social_awareness": 1,
        "impression": 0.5,
    },
    "gesture_response_success": {
        "perceived_dexterity": 1,
        "perceived_safety": 2,
        "perceived_social_awareness": 3,
        "impression": 2,
    },
    "acknowledgement_clarity": {
        "perceived_dexterity": 1,
        "perceived_safety": 2,
        "perceived_social_awareness": 3,
        "impression": 2,
    },
    "human_aware_approach": {
        "perceived_dexterity": 1,
        "perceived_safety": 3,
        "perceived_social_awareness": 3,
        "impression": 2,
    },
    "bystander_ack": {
        "perceived_dexterity": 1,
        "perceived_safety": 2,
        "perceived_social_awareness": 3,
        "impression": 1,
    },
    "sparc": {
        "perceived_dexterity": 1,
        "perceived_safety": 0.5,
        "perceived_social_awareness": 0,
        "impression": 1,
    },
    "heading_jerk": {
        "perceived_dexterity": 1,
        "perceived_safety": 1,
        "perceived_social_awareness": 0,
        "impression": 1.5,
    },
    "stability": {
        "perceived_dexterity": 2,
        "perceived_safety": 3,
        "perceived_social_awareness": 0,
        "impression": 1,
    },
    "legibility": {
        "perceived_dexterity": 2,
        "perceived_safety": 1,
        "perceived_social_awareness": 3,
        "impression": 1,
    },
    "behavioral_naturalness": {
        "perceived_dexterity": 1,
        "perceived_safety": 0,
        "perceived_social_awareness": 0,
        "impression": 2,
    },
}


def normalized_axis_weights(
    axis_id: str,
    evidence_weights: Mapping[str, Mapping[str, float]] = V1_EVIDENCE_WEIGHTS,
) -> dict[str, float]:
    if axis_id not in SOCIAL_NAVIGATION_AXIS_IDS:
        raise ValueError(f"unknown axis id: {axis_id}")
    _validate_weight_matrix(evidence_weights)
    total = fsum(row[axis_id] for row in evidence_weights.values())
    if total <= 0:
        raise ValueError(f"axis has no positive weights: {axis_id}")
    return {
        feature_id: row[axis_id] / total
        for feature_id, row in evidence_weights.items()
        if row[axis_id] > 0
    }


def axis_weight_sums(
    evidence_weights: Mapping[str, Mapping[str, float]] = V1_EVIDENCE_WEIGHTS,
) -> dict[str, float]:
    _validate_weight_matrix(evidence_weights)
    return {
        axis_id: fsum(row[axis_id] for row in evidence_weights.values())
        for axis_id in SOCIAL_NAVIGATION_AXIS_IDS
    }


def _validate_weight_matrix(evidence_weights: Mapping[str, Mapping[str, float]]) -> None:
    feature_ids = set(evidence_weights)
    if feature_ids != set(SOCIAL_NAVIGATION_METRIC_IDS):
        raise ValueError("weight matrix feature ids must match social-navigation metric ids")
    for feature_id, row in evidence_weights.items():
        axis_ids = set(row)
        if axis_ids != set(SOCIAL_NAVIGATION_AXIS_IDS):
            raise ValueError(f"weight row has invalid axes: {feature_id}")
        for axis_id, weight in row.items():
            if weight < 0:
                raise ValueError(f"weight must be non-negative: {feature_id}.{axis_id}")

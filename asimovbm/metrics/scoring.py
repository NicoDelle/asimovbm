"""Shared score helpers for metric report aggregation."""

from __future__ import annotations

from collections.abc import Mapping
from math import fsum
from typing import Any

from .models import SOCIAL_NAVIGATION_AXIS_IDS, MetricStatus
from .weights import WEIGHT_MODEL_KIND, WEIGHT_MODEL_SOURCE, WEIGHT_MODEL_VERSION


def default_axis_scoring_model() -> dict[str, str]:
    return {
        "kind": WEIGHT_MODEL_KIND,
        "version": WEIGHT_MODEL_VERSION,
        "source": WEIGHT_MODEL_SOURCE,
    }


def global_score_from_axes(
    axes: Mapping[str, dict[str, Any]],
    *,
    cap_key: str = "applied_caps",
    axis_model: str = WEIGHT_MODEL_KIND,
    extra_model_metadata: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    computed_axes = [
        axis
        for axis in axes.values()
        if axis.get("status") == MetricStatus.COMPUTED.value
        and isinstance(axis.get("score"), int | float)
    ]
    model = global_score_model(axis_model=axis_model, extra=extra_model_metadata)
    if not computed_axes:
        return {
            "status": MetricStatus.NOT_APPLICABLE.value,
            "score": None,
            "confidence": "not_applicable",
            "contributing_axes": (),
            "model_metadata": model,
            "reason": "no computed axis scores",
        }
    evidence_gaps = _global_evidence_gaps(computed_axes)
    if evidence_gaps:
        return {
            "status": MetricStatus.INSUFFICIENT_EVIDENCE.value,
            "score": None,
            "confidence": "insufficient",
            "contributing_axes": tuple(axis["axis_id"] for axis in computed_axes),
            "model_metadata": model,
            "reason": "one or more contributing axes omitted required evidence",
            "evidence_gaps": tuple(evidence_gaps),
        }
    raw_score = fsum(float(axis["score"]) for axis in computed_axes) / len(computed_axes)
    score, applied_caps = apply_global_score_caps(raw_score, axes, cap_key=cap_key)
    return {
        "status": MetricStatus.COMPUTED.value,
        "score": snap_score(score),
        "confidence": "sufficient" if len(computed_axes) == len(SOCIAL_NAVIGATION_AXIS_IDS) else "partial",
        "contributing_axes": tuple(axis["axis_id"] for axis in computed_axes),
        "model_metadata": model,
        "applied_caps": applied_caps,
    }


def apply_global_score_caps(
    score: float,
    axes: Mapping[str, dict[str, Any]],
    *,
    cap_key: str,
) -> tuple[float, tuple[dict[str, object], ...]]:
    safety = axes.get("perceived_safety", {})
    safety_score = safety.get("score")
    safety_caps = tuple(safety.get(cap_key, ()))
    if not safety_caps or not isinstance(safety_score, int | float):
        return score, ()

    source_caps = [
        float(cap["cap"])
        for cap in safety_caps
        if isinstance(cap, Mapping) and isinstance(cap.get("cap"), int | float)
    ]
    cap_value = min(source_caps) if source_caps else float(safety_score)
    capped_score = min(score, cap_value)
    if capped_score == score:
        return score, ()
    return capped_score, (
        {
            "kind": "v1_safety_axis_global_cap",
            "cap": cap_value,
            "source_axis": "perceived_safety",
            "source": WEIGHT_MODEL_SOURCE,
        },
    )


def global_score_model(
    *,
    axis_model: str = WEIGHT_MODEL_KIND,
    extra: Mapping[str, str] | None = None,
) -> dict[str, str]:
    model = {
        "kind": "equal_weight_axis_mean_with_v1_caps",
        "version": WEIGHT_MODEL_VERSION,
        "source": WEIGHT_MODEL_SOURCE,
        "axis_model": axis_model,
    }
    if extra is not None:
        model.update(extra)
    return model


def _global_evidence_gaps(computed_axes: list[dict[str, Any]]) -> list[dict[str, object]]:
    gaps: list[dict[str, object]] = []
    insufficient_statuses = {
        MetricStatus.INSUFFICIENT_EVIDENCE.value,
        MetricStatus.INVALID_INPUT.value,
        "missing",
    }
    for axis in computed_axes:
        omitted = axis.get("omitted_feature_statuses", {})
        if isinstance(omitted, Mapping):
            missing_features = tuple(
                feature_id
                for feature_id, status in omitted.items()
                if status in insufficient_statuses
            )
            if missing_features:
                gaps.append(
                    {
                        "axis_id": axis.get("axis_id"),
                        "missing_features": missing_features,
                    }
                )
        source_gaps = axis.get("source_episode_evidence_gaps", ())
        if source_gaps:
            gaps.append(
                {
                    "axis_id": axis.get("axis_id"),
                    "source_episode_evidence_gaps": tuple(source_gaps),
                }
            )
    return gaps


def snap_score(score: float) -> float:
    bounded = min(1.0, max(0.0, score))
    if abs(bounded - 1.0) < 1e-12:
        return 1.0
    if abs(bounded) < 1e-12:
        return 0.0
    return bounded

"""Compare objective predictions with subjective survey outcomes."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from .analysis import aggregate_video_scores, ks_distance, rank_correlation, weighted_global_score
from .survey_design import GLOBAL_WEIGHT_PRESETS, SURVEY_AXIS_IDS, validate_weight_preset
from .video_manifest import SurveyVideo


def compare_predictions_with_survey(
    videos: Sequence[SurveyVideo],
    *,
    predictions: Mapping[str, Mapping[str, Any]],
    responses: Sequence[Mapping[str, Any]],
    weight_preset: str = "equal",
) -> dict[str, Any]:
    weights = validate_weight_preset(GLOBAL_WEIGHT_PRESETS[weight_preset])
    aggregate = aggregate_video_scores(responses, weight_preset=weight_preset)
    per_video: dict[str, dict[str, Any]] = {}
    survey_global: dict[str, float] = {}
    prediction_global: dict[str, float] = {}
    survey_axis_samples: list[float] = []
    prediction_axis_samples: list[float] = []

    for video in sorted(videos, key=lambda item: (item.episode_order, item.video_id)):
        survey_payload = aggregate["videos"].get(video.video_id)
        prediction_payload = predictions.get(video.video_id, {})
        prediction_axes = _prediction_axes(prediction_payload)
        survey_axes = _survey_axes(survey_payload)
        shared_axes = sorted(set(prediction_axes) & set(survey_axes))
        prediction_value = weighted_global_score(prediction_axes, weights)
        survey_value = weighted_global_score(survey_axes, weights)
        if prediction_value is not None:
            prediction_global[video.video_id] = prediction_value
        if survey_value is not None:
            survey_global[video.video_id] = survey_value
        survey_axis_samples.extend(survey_axes[axis_id] for axis_id in shared_axes)
        prediction_axis_samples.extend(prediction_axes[axis_id] for axis_id in shared_axes)
        per_video[video.video_id] = {
            "status": _comparison_status(
                prediction_payload=prediction_payload,
                prediction_axes=prediction_axes,
                survey_axes=survey_axes,
                shared_axes=shared_axes,
            ),
            "video": _video_metadata(video),
            "prediction_status": prediction_payload.get("status", "missing_prediction"),
            "prediction_axes": _axis_payload(prediction_axes),
            "survey_axes": _axis_payload(survey_axes),
            "axis_absolute_errors": {
                axis_id: abs(prediction_axes[axis_id] - survey_axes[axis_id])
                for axis_id in shared_axes
            },
            "prediction_global": prediction_value,
            "survey_global": survey_value,
            "global_absolute_error": abs(prediction_value - survey_value)
            if prediction_value is not None and survey_value is not None
            else None,
            "survey_response_count": _survey_response_count(survey_payload),
            "diagnostics": list(prediction_payload.get("diagnostics", ())),
        }

    shared_video_ids = sorted(set(survey_global) & set(prediction_global))
    return {
        "schema_version": "asimovbm.prediction_survey_comparison.v1",
        "weight_preset": weight_preset,
        "aggregate": aggregate,
        "videos": per_video,
        "groups": _group_summaries(videos, per_video),
        "rank_order_correlation": rank_correlation(
            [prediction_global[video_id] for video_id in shared_video_ids],
            [survey_global[video_id] for video_id in shared_video_ids],
        ),
        "distribution_distance": ks_distance(prediction_axis_samples, survey_axis_samples),
        "diagnostics": list(aggregate.get("diagnostics", ())),
    }


def _prediction_axes(payload: Mapping[str, Any]) -> dict[str, float]:
    axes_payload = payload.get("axes", {})
    if not isinstance(axes_payload, Mapping):
        return {}
    return _scores_from_axis_payload(axes_payload, score_key="score")


def _survey_axes(payload: Mapping[str, Any] | None) -> dict[str, float]:
    if not isinstance(payload, Mapping):
        return {}
    axes_payload = payload.get("axes", {})
    if not isinstance(axes_payload, Mapping):
        return {}
    return _scores_from_axis_payload(axes_payload, score_key="mean")


def _scores_from_axis_payload(
    axes_payload: Mapping[str, Any],
    *,
    score_key: str,
) -> dict[str, float]:
    scores: dict[str, float] = {}
    for axis_id in SURVEY_AXIS_IDS:
        axis = axes_payload.get(axis_id)
        if isinstance(axis, Mapping) and isinstance(axis.get(score_key), int | float):
            scores[axis_id] = float(axis[score_key])
    return scores


def _axis_payload(scores: Mapping[str, float]) -> dict[str, float | None]:
    return {axis_id: scores.get(axis_id) for axis_id in SURVEY_AXIS_IDS}


def _comparison_status(
    *,
    prediction_payload: Mapping[str, Any],
    prediction_axes: Mapping[str, float],
    survey_axes: Mapping[str, float],
    shared_axes: Sequence[str],
) -> str:
    if not prediction_payload or prediction_payload.get("status") == "missing_source":
        return "missing_prediction"
    if not prediction_axes:
        return "missing_prediction_axes"
    if not survey_axes:
        return "missing_survey"
    if not shared_axes:
        return "no_shared_axes"
    return "compared"


def _survey_response_count(payload: Mapping[str, Any] | None) -> int:
    if not isinstance(payload, Mapping):
        return 0
    axes_payload = payload.get("axes", {})
    if not isinstance(axes_payload, Mapping):
        return 0
    return max(
        (
            int(axis.get("count", 0))
            for axis in axes_payload.values()
            if isinstance(axis, Mapping)
        ),
        default=0,
    )


def _video_metadata(video: SurveyVideo) -> dict[str, Any]:
    return {
        "video_id": video.video_id,
        "title": video.title,
        "path": video.path,
        "policy_id": video.policy_id,
        "viewpoint": video.viewpoint,
        "robot_id": video.robot_id,
        "episode_id": video.episode_id,
        "episode_order": video.episode_order,
        "group_ids": list(video.group_ids),
        "metrics": dict(video.metrics),
    }


def _group_summaries(
    videos: Sequence[SurveyVideo],
    per_video: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    by_group: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for video in videos:
        comparison = per_video.get(video.video_id)
        if comparison is None:
            continue
        for group_id in video.group_ids:
            by_group[group_id].append(comparison)
    return {
        group_id: {
            "video_count": len(items),
            "compared_count": sum(1 for item in items if item.get("status") == "compared"),
            "prediction_global_mean": _mean(
                item.get("prediction_global") for item in items
            ),
            "survey_global_mean": _mean(item.get("survey_global") for item in items),
            "global_absolute_error_mean": _mean(
                item.get("global_absolute_error") for item in items
            ),
        }
        for group_id, items in sorted(by_group.items())
    }


def _mean(values: Sequence[Any]) -> float | None:
    numeric = [float(value) for value in values if isinstance(value, int | float)]
    if not numeric:
        return None
    return sum(numeric) / len(numeric)

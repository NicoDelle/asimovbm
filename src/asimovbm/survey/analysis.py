"""Survey aggregation and objective-vs-subjective comparison helpers."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from math import sqrt
from typing import Any

from .survey_design import GLOBAL_WEIGHT_PRESETS, SURVEY_AXIS_IDS, validate_weight_preset


def aggregate_video_scores(
    responses: Sequence[Mapping[str, Any]],
    *,
    weight_preset: str = "equal",
) -> dict[str, Any]:
    weights = validate_weight_preset(GLOBAL_WEIGHT_PRESETS[weight_preset])
    axis_values: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    q5_values: dict[str, list[float]] = defaultdict(list)
    diagnostics: list[dict[str, Any]] = []
    for response in responses:
        video_id = str(response.get("video_id", ""))
        if not video_id:
            diagnostics.append({"reason": "missing video_id", "response": dict(response)})
            continue
        answers = response.get("answers", {})
        if not isinstance(answers, Mapping):
            diagnostics.append({"video_id": video_id, "reason": "answers is not an object"})
            continue
        for question_id, answer in answers.items():
            if not isinstance(answer, Mapping):
                diagnostics.append(
                    {"video_id": video_id, "question_id": question_id, "reason": "answer is invalid"}
                )
                continue
            score = answer.get("score_0_100")
            axis_id = answer.get("axis_id")
            if not isinstance(score, int | float):
                continue
            if axis_id in SURVEY_AXIS_IDS and answer.get("primary_score", True):
                axis_values[video_id][str(axis_id)].append(float(score))
            elif question_id == "appropriate_behavior":
                q5_values[video_id].append(float(score))
    videos: dict[str, dict[str, Any]] = {}
    for video_id, axis_map in axis_values.items():
        axes: dict[str, dict[str, Any]] = {}
        for axis_id in SURVEY_AXIS_IDS:
            values = axis_map.get(axis_id, [])
            axes[axis_id] = {
                "mean": _mean(values),
                "count": len(values),
            }
        global_score = weighted_global_score(
            {
                axis_id: axes[axis_id]["mean"]
                for axis_id in SURVEY_AXIS_IDS
                if axes[axis_id]["mean"] is not None
            },
            weights,
        )
        videos[video_id] = {
            "video_id": video_id,
            "axes": axes,
            "global_score": global_score,
            "weight_preset": weight_preset,
            "q5": {
                "mean": _mean(q5_values.get(video_id, [])),
                "count": len(q5_values.get(video_id, [])),
            },
        }
    return {
        "schema_version": "asimovbm.survey_aggregate.v1",
        "weight_preset": weight_preset,
        "videos": videos,
        "diagnostics": diagnostics,
    }


def compare_with_testbench(
    survey_scores: Mapping[str, Mapping[str, Any]],
    testbench_scores: Mapping[str, Mapping[str, float]],
    *,
    weight_preset: str = "equal",
) -> dict[str, Any]:
    weights = validate_weight_preset(GLOBAL_WEIGHT_PRESETS[weight_preset])
    per_video: dict[str, dict[str, Any]] = {}
    survey_global: dict[str, float] = {}
    testbench_global: dict[str, float] = {}
    survey_axis_samples: list[float] = []
    testbench_axis_samples: list[float] = []
    for video_id, survey_payload in survey_scores.items():
        objective_axes = testbench_scores.get(video_id)
        if objective_axes is None:
            per_video[video_id] = {"status": "missing_testbench"}
            continue
        survey_axes_payload = survey_payload.get("axes", {})
        survey_axes = {
            axis_id: survey_axes_payload.get(axis_id, {}).get("mean")
            for axis_id in SURVEY_AXIS_IDS
        }
        survey_axes = {
            axis_id: float(value)
            for axis_id, value in survey_axes.items()
            if isinstance(value, int | float)
        }
        objective_axes = {
            axis_id: float(objective_axes[axis_id])
            for axis_id in SURVEY_AXIS_IDS
            if axis_id in objective_axes
        }
        shared_axes = sorted(set(survey_axes) & set(objective_axes))
        axis_errors = {
            axis_id: abs(survey_axes[axis_id] - objective_axes[axis_id])
            for axis_id in shared_axes
        }
        survey_value = weighted_global_score(survey_axes, weights)
        objective_value = weighted_global_score(objective_axes, weights)
        if survey_value is not None and objective_value is not None:
            survey_global[video_id] = survey_value
            testbench_global[video_id] = objective_value
        survey_axis_samples.extend(survey_axes[axis_id] for axis_id in shared_axes)
        testbench_axis_samples.extend(objective_axes[axis_id] for axis_id in shared_axes)
        per_video[video_id] = {
            "status": "compared" if shared_axes else "no_shared_axes",
            "axis_absolute_errors": axis_errors,
            "global_absolute_error": abs(survey_value - objective_value)
            if survey_value is not None and objective_value is not None
            else None,
            "survey_global": survey_value,
            "testbench_global": objective_value,
        }
    shared_video_ids = sorted(set(survey_global) & set(testbench_global))
    return {
        "schema_version": "asimovbm.survey_testbench_comparison.v1",
        "weight_preset": weight_preset,
        "per_video": per_video,
        "rank_order_correlation": rank_correlation(
            [survey_global[video_id] for video_id in shared_video_ids],
            [testbench_global[video_id] for video_id in shared_video_ids],
        ),
        "distribution_distance": ks_distance(survey_axis_samples, testbench_axis_samples),
    }


def weighted_global_score(
    axis_scores: Mapping[str, float | None],
    weights: Mapping[str, float],
) -> float | None:
    scored = {
        axis_id: float(score)
        for axis_id, score in axis_scores.items()
        if axis_id in weights and score is not None
    }
    if not scored:
        return None
    active_total = sum(weights[axis_id] for axis_id in scored)
    return sum(scored[axis_id] * (weights[axis_id] / active_total) for axis_id in scored)


def rank_correlation(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    return pearson_correlation(_ranks(left), _ranks(right))


def pearson_correlation(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    left_mean = _mean(left)
    right_mean = _mean(right)
    if left_mean is None or right_mean is None:
        return None
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right, strict=True))
    left_var = sum((a - left_mean) ** 2 for a in left)
    right_var = sum((b - right_mean) ** 2 for b in right)
    denominator = sqrt(left_var * right_var)
    if denominator == 0.0:
        return None
    return numerator / denominator


def ks_distance(left: Sequence[float], right: Sequence[float]) -> float | None:
    if not left or not right:
        return None
    left_sorted = sorted(float(value) for value in left)
    right_sorted = sorted(float(value) for value in right)
    points = sorted(set(left_sorted + right_sorted))
    max_distance = 0.0
    left_index = 0
    right_index = 0
    for point in points:
        while left_index < len(left_sorted) and left_sorted[left_index] <= point:
            left_index += 1
        while right_index < len(right_sorted) and right_sorted[right_index] <= point:
            right_index += 1
        distance = abs(left_index / len(left_sorted) - right_index / len(right_sorted))
        max_distance = max(max_distance, distance)
    return max_distance


def _mean(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return sum(float(value) for value in values) / len(values)


def _ranks(values: Sequence[float]) -> list[float]:
    indexed = sorted((float(value), index) for index, value in enumerate(values))
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(indexed):
        end = cursor + 1
        while end < len(indexed) and indexed[end][0] == indexed[cursor][0]:
            end += 1
        rank = (cursor + 1 + end) / 2.0
        for _, original_index in indexed[cursor:end]:
            ranks[original_index] = rank
        cursor = end
    return ranks

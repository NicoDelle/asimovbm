from __future__ import annotations

from asimovbm.survey.analysis import (
    aggregate_video_scores,
    compare_with_testbench,
    ks_distance,
    rank_correlation,
)


def _response(video_id: str, participant_id: str, values: tuple[int, int, int, int]):
    axes = (
        "perceived_dexterity",
        "perceived_safety",
        "perceived_social_awareness",
        "impression",
    )
    questions = (
        "competent_control",
        "safe_behavior",
        "surrounding_awareness",
        "positive_impression",
    )
    return {
        "participant_id": participant_id,
        "video_id": video_id,
        "answers": {
            question_id: {
                "likert": value,
                "score_0_100": value,
                "axis_id": axis_id,
                "primary_score": True,
            }
            for question_id, axis_id, value in zip(questions, axes, values, strict=True)
        },
    }


def test_aggregate_video_scores_returns_axis_means_and_global_score() -> None:
    aggregate = aggregate_video_scores(
        [
            _response("video-1", "p1", (100, 50, 50, 100)),
            _response("video-1", "p2", (0, 50, 50, 0)),
        ]
    )

    video = aggregate["videos"]["video-1"]
    assert video["axes"]["perceived_dexterity"] == {"mean": 50.0, "count": 2}
    assert video["global_score"] == 50.0


def test_global_score_changes_for_safety_sensitive_weights() -> None:
    equal = aggregate_video_scores([_response("video-1", "p1", (100, 0, 0, 0))])
    safety = aggregate_video_scores(
        [_response("video-1", "p1", (100, 0, 0, 0))],
        weight_preset="safety_sensitive",
    )

    assert equal["videos"]["video-1"]["global_score"] == 25
    assert safety["videos"]["video-1"]["global_score"] == 20


def test_rank_correlation_is_positive_for_matching_order() -> None:
    assert rank_correlation([10, 20, 30], [1, 2, 3]) == 1


def test_ks_distance_returns_zero_for_matching_distributions() -> None:
    assert ks_distance([10, 20, 30], [10, 20, 30]) == 0


def test_compare_with_testbench_reports_global_errors_and_rank_correlation() -> None:
    survey = aggregate_video_scores(
        [
            _response("video-a", "p1", (90, 90, 90, 90)),
            _response("video-b", "p1", (10, 10, 10, 10)),
        ]
    )["videos"]
    comparison = compare_with_testbench(
        survey,
        {
            "video-a": {
                "perceived_dexterity": 80,
                "perceived_safety": 80,
                "perceived_social_awareness": 80,
                "impression": 80,
            },
            "video-b": {
                "perceived_dexterity": 20,
                "perceived_safety": 20,
                "perceived_social_awareness": 20,
                "impression": 20,
            },
        },
    )

    assert comparison["per_video"]["video-a"]["global_absolute_error"] == 10
    assert comparison["rank_order_correlation"] == 1

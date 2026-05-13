from __future__ import annotations

from asimovbm.survey.comparison import compare_predictions_with_survey
from asimovbm.survey.video_manifest import SurveyVideo


def _video(video_id: str, group_id: str) -> SurveyVideo:
    return SurveyVideo(
        video_id=video_id,
        path=f"{video_id}.mp4",
        policy_id="policy_a",
        viewpoint="first_person",
        robot_id="g1",
        episode_id=video_id,
        group_ids=(group_id,),
    )


def _response(video_id: str, value: int) -> dict:
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
        "participant_id": "p1",
        "video_id": video_id,
        "answers": {
            question_id: {
                "likert": value,
                "score_0_100": value,
                "axis_id": axis_id,
                "primary_score": True,
            }
            for question_id, axis_id in zip(questions, axes, strict=True)
        },
    }


def test_compare_predictions_with_survey_reports_group_and_rank_metrics() -> None:
    videos = (_video("video-a", "policy_a_fp"), _video("video-b", "policy_a_fp"))
    predictions = {
        "video-a": {
            "status": "computed",
            "axes": {
                "perceived_dexterity": {"score": 80},
                "perceived_safety": {"score": 80},
                "perceived_social_awareness": {"score": 80},
                "impression": {"score": 80},
            },
        },
        "video-b": {
            "status": "computed",
            "axes": {
                "perceived_dexterity": {"score": 20},
                "perceived_safety": {"score": 20},
                "perceived_social_awareness": {"score": 20},
                "impression": {"score": 20},
            },
        },
    }

    comparison = compare_predictions_with_survey(
        videos,
        predictions=predictions,
        responses=[_response("video-a", 90), _response("video-b", 10)],
    )

    assert comparison["videos"]["video-a"]["status"] == "compared"
    assert comparison["videos"]["video-a"]["global_absolute_error"] == 10
    assert comparison["groups"]["policy_a_fp"]["compared_count"] == 2
    assert comparison["rank_order_correlation"] == 1

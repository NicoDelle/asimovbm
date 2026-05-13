from __future__ import annotations

from pathlib import Path

import pytest

from asimovbm.survey.storage import SurveyStorageError, SurveyStore
from asimovbm.survey.video_manifest import parse_video_manifest


def _manifest(tmp_path: Path):
    return parse_video_manifest(
        {
            "study_id": "pilot",
            "videos": [
                {
                    "video_id": "video-1",
                    "path": "video-1.mp4",
                    "policy_id": "policy_a",
                    "viewpoint": "first_person",
                    "robot_id": "g1",
                    "episode_id": "g1_approach_user",
                    "group_ids": ["policy_a_fp"],
                    "episode_order": 1,
                }
            ],
        },
        video_root=tmp_path,
    )


def test_start_participant_writes_metadata_record(tmp_path: Path) -> None:
    store = SurveyStore(tmp_path / "survey", "pilot")

    record = store.start_participant(
        group_id="policy_a_fp",
        participant_id="p1",
        assigned_video_ids=("video-1",),
        metadata={"robotics_familiarity": "basic"},
    )

    assert record["participant_id"] == "p1"
    assert store.participants()[0]["metadata"]["robotics_familiarity"] == "basic"


def test_append_response_maps_likert_answers_to_scores(tmp_path: Path) -> None:
    store = SurveyStore(tmp_path / "survey", "pilot")
    store.start_participant(
        group_id="policy_a_fp",
        participant_id="p1",
        assigned_video_ids=("video-1",),
    )

    response = store.append_response(
        {
            "participant_id": "p1",
            "group_id": "policy_a_fp",
            "video_id": "video-1",
            "answers": {
                "competent_control": 7,
                "safe_behavior": 4,
                "surrounding_awareness": 1,
                "positive_impression": 4,
            },
        },
        manifest=_manifest(tmp_path),
    )

    assert response["answers"]["competent_control"]["score_0_100"] == 100
    assert response["answers"]["safe_behavior"]["score_0_100"] == 50
    assert store.latest_participants()["p1"]["completion_status"] == "completed"


def test_partial_response_is_rejected(tmp_path: Path) -> None:
    store = SurveyStore(tmp_path / "survey", "pilot")

    with pytest.raises(SurveyStorageError):
        store.append_response(
            {
                "participant_id": "p1",
                "group_id": "policy_a_fp",
                "video_id": "video-1",
                "answers": {"competent_control": 7},
            },
            manifest=_manifest(tmp_path),
        )

    assert store.responses() == ()


def test_optional_q5_is_stored_when_enabled(tmp_path: Path) -> None:
    store = SurveyStore(tmp_path / "survey", "pilot")

    response = store.append_response(
        {
            "participant_id": "p1",
            "group_id": "policy_a_fp",
            "video_id": "video-1",
            "answers": {
                "competent_control": 7,
                "safe_behavior": 7,
                "surrounding_awareness": 7,
                "positive_impression": 7,
                "appropriate_behavior": 4,
            },
        },
        manifest=_manifest(tmp_path),
        include_q5=True,
    )

    assert response["answers"]["appropriate_behavior"]["primary_score"] is False

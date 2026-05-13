from __future__ import annotations

from pathlib import Path

from asimovbm.survey.export import (
    build_participant_rows,
    participants_csv_text,
    write_participants_csv,
)
from asimovbm.survey.storage import SurveyStore


def test_participant_rows_include_completion_counts_and_metadata() -> None:
    rows = build_participant_rows(
        [
            {
                "participant_id": "p1",
                "group_id": "policy_a_fp",
                "policy_id": "policy_a",
                "viewpoint": "first_person",
                "robot_id": "g1",
                "assigned_video_ids": ["video-1", "video-2"],
                "assigned_video_count": 2,
                "completion_status": "started",
                "started_at": "2026-05-13T10:00:00+00:00",
                "completed_at": None,
                "metadata": {"robotics_familiarity": "basic"},
            }
        ],
        [
            {
                "participant_id": "p1",
                "video_id": "video-1",
                "answers": {"appropriate_behavior": {"score_0_100": 50}},
            }
        ],
    )

    assert rows[0]["completed_video_count"] == 1
    assert rows[0]["completion_status"] == "started"
    assert rows[0]["robotics_familiarity"] == "basic"
    assert rows[0]["q5_answered"] == "yes"


def test_participants_csv_text_has_header_and_rows() -> None:
    csv_text = participants_csv_text(
        [
            {
                "participant_id": "p1",
                "group_id": "policy_a_fp",
                "policy_id": "policy_a",
                "viewpoint": "first_person",
                "robot_id": "g1",
                "assigned_video_ids": ["video-1"],
                "assigned_video_count": 1,
                "metadata": {},
            }
        ],
        [],
    )

    assert csv_text.splitlines()[0].startswith("participant_id,group_id")
    assert "p1,policy_a_fp" in csv_text


def test_write_participants_csv_writes_export_file(tmp_path: Path) -> None:
    store = SurveyStore(tmp_path, "pilot")
    store.start_participant(
        group_id="policy_a_fp",
        participant_id="p1",
        assigned_video_ids=("video-1",),
    )

    output = write_participants_csv(store)

    assert output == tmp_path / "pilot" / "participants.csv"
    assert output.read_text(encoding="utf-8").splitlines()[1].startswith("p1,")

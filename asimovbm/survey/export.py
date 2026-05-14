"""CSV export helpers for survey participant metadata."""

from __future__ import annotations

import csv
from collections import defaultdict
from collections.abc import Mapping, Sequence
from io import StringIO
from pathlib import Path
from typing import Any

from .storage import SurveyStore
from .survey_design import DEFAULT_PARTICIPANT_FIELDS

PARTICIPANT_BASE_COLUMNS: tuple[str, ...] = (
    "participant_id",
    "group_id",
    "policy_id",
    "viewpoint",
    "robot_id",
    "assigned_video_ids",
    "assigned_video_count",
    "completed_video_count",
    "completion_status",
    "started_at",
    "completed_at",
    "q5_answered",
)


def participant_csv_columns() -> tuple[str, ...]:
    return PARTICIPANT_BASE_COLUMNS + tuple(
        field.csv_column for field in DEFAULT_PARTICIPANT_FIELDS
    )


def build_participant_rows(
    participants: Sequence[Mapping[str, Any]],
    responses: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    latest: dict[str, Mapping[str, Any]] = {}
    for participant in participants:
        latest[str(participant["participant_id"])] = participant
    completed_videos: dict[str, set[str]] = defaultdict(set)
    q5_answered: dict[str, bool] = defaultdict(bool)
    for response in responses:
        participant_id = str(response.get("participant_id", ""))
        if not participant_id:
            continue
        completed_videos[participant_id].add(str(response.get("video_id", "")))
        answers = response.get("answers", {})
        if isinstance(answers, Mapping) and "appropriate_behavior" in answers:
            q5_answered[participant_id] = True
    rows: list[dict[str, Any]] = []
    for participant_id in sorted(latest):
        participant = latest[participant_id]
        metadata = participant.get("metadata", {})
        if not isinstance(metadata, Mapping):
            metadata = {}
        assigned_video_ids = tuple(str(video_id) for video_id in participant.get("assigned_video_ids", ()))
        assigned_count = int(participant.get("assigned_video_count") or len(assigned_video_ids))
        completed_count = len(completed_videos.get(participant_id, set()))
        status = str(participant.get("completion_status") or "started")
        if assigned_count > 0 and completed_count >= assigned_count:
            status = "completed"
        row = {
            "participant_id": participant_id,
            "group_id": participant.get("group_id", ""),
            "policy_id": participant.get("policy_id", ""),
            "viewpoint": participant.get("viewpoint", ""),
            "robot_id": participant.get("robot_id", ""),
            "assigned_video_ids": "|".join(assigned_video_ids),
            "assigned_video_count": assigned_count,
            "completed_video_count": completed_count,
            "completion_status": status,
            "started_at": participant.get("started_at", ""),
            "completed_at": participant.get("completed_at", ""),
            "q5_answered": "yes" if q5_answered.get(participant_id) else "no",
        }
        for field in DEFAULT_PARTICIPANT_FIELDS:
            row[field.csv_column] = metadata.get(field.id, "")
        rows.append(row)
    return rows


def participants_csv_text(
    participants: Sequence[Mapping[str, Any]],
    responses: Sequence[Mapping[str, Any]],
) -> str:
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=participant_csv_columns(), lineterminator="\n")
    writer.writeheader()
    for row in build_participant_rows(participants, responses):
        writer.writerow(row)
    return output.getvalue()


def write_participants_csv(store: SurveyStore, output_path: Path | None = None) -> Path:
    path = output_path or store.study_dir / "participants.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        participants_csv_text(store.participants(), store.responses()),
        encoding="utf-8",
    )
    return path

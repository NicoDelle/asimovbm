"""Append-only local survey participant and response storage."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .survey_design import (
    CORE_QUESTIONS,
    OPTIONAL_Q5,
    SurveyDesignError,
    get_question,
    get_study_cell,
    likert_to_score,
    validate_participant_metadata,
)
from .video_manifest import SurveyVideoManifest


class SurveyStorageError(ValueError):
    """Raised when survey records cannot be stored or validated."""


class SurveyStore:
    """Local append-only JSONL store for one survey study."""

    def __init__(self, survey_root: Path | str, study_id: str) -> None:
        self.survey_root = Path(survey_root)
        self.study_id = study_id
        self.study_dir = self.survey_root / study_id
        self.participants_path = self.study_dir / "participants.jsonl"
        self.responses_path = self.study_dir / "responses.jsonl"

    def start_participant(
        self,
        *,
        group_id: str,
        assigned_video_ids: tuple[str, ...],
        participant_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        cell = get_study_cell(group_id)
        participant_metadata = validate_participant_metadata(metadata or {})
        timestamp = _timestamp(now)
        record = {
            "schema_version": "asimovbm.survey_participant.v1",
            "study_id": self.study_id,
            "participant_id": participant_id or _participant_id(),
            "group_id": group_id,
            "policy_id": cell.policy_id,
            "viewpoint": cell.viewpoint,
            "robot_id": cell.robot_id,
            "assigned_video_ids": list(assigned_video_ids),
            "assigned_video_count": len(assigned_video_ids),
            "completion_status": "started",
            "started_at": timestamp,
            "completed_at": None,
            "metadata": participant_metadata,
            "recorded_at": timestamp,
        }
        self._append_jsonl(self.participants_path, record)
        return record

    def next_quota_group(
        self,
        eligible_group_ids: tuple[str, ...],
        *,
        quota_per_group: int,
    ) -> str:
        if not eligible_group_ids:
            raise SurveyStorageError("no survey groups have assigned videos")
        completed_counts = self.completed_counts_by_group()
        candidates = [
            (completed_counts.get(group_id, 0), index, group_id)
            for index, group_id in enumerate(eligible_group_ids)
            if completed_counts.get(group_id, 0) < quota_per_group
        ]
        if not candidates:
            raise SurveyStorageError("survey quota is full")
        _, _, group_id = min(candidates)
        return group_id

    def completed_counts_by_group(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for participant in self.latest_participants().values():
            if participant.get("completion_status") != "completed":
                continue
            group_id = str(participant.get("group_id", ""))
            if group_id:
                counts[group_id] = counts.get(group_id, 0) + 1
        return counts

    def append_response(
        self,
        payload: Mapping[str, Any],
        *,
        manifest: SurveyVideoManifest,
        include_q5: bool = False,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        participant_id = str(payload.get("participant_id", ""))
        if not participant_id:
            raise SurveyStorageError("participant_id is required")
        group_id = str(payload.get("group_id", ""))
        cell = get_study_cell(group_id)
        video = manifest.get_video(str(payload.get("video_id", "")))
        if group_id not in video.group_ids:
            raise SurveyStorageError("video is not assigned to participant group")
        answers = _validate_answers(payload.get("answers", {}), include_q5=include_q5)
        timestamp = _timestamp(now)
        record = {
            "schema_version": "asimovbm.survey_response.v1",
            "study_id": self.study_id,
            "participant_id": participant_id,
            "group_id": group_id,
            "policy_id": video.policy_id or cell.policy_id,
            "viewpoint": video.viewpoint or cell.viewpoint,
            "robot_id": video.robot_id,
            "video_id": video.video_id,
            "episode_id": video.episode_id,
            "episode_order": int(payload.get("episode_order", video.episode_order)),
            "answers": answers,
            "video_completed": bool(payload.get("video_completed", False)),
            "submitted_at": timestamp,
        }
        self._append_jsonl(self.responses_path, record)
        self._append_completion_if_finished(record, now=now)
        return record

    def participants(self) -> tuple[dict[str, Any], ...]:
        return tuple(_read_jsonl(self.participants_path))

    def latest_participants(self) -> dict[str, dict[str, Any]]:
        latest: dict[str, dict[str, Any]] = {}
        for record in self.participants():
            latest[str(record["participant_id"])] = record
        return latest

    def responses(self) -> tuple[dict[str, Any], ...]:
        return tuple(_read_jsonl(self.responses_path))

    def _append_completion_if_finished(
        self,
        response_record: Mapping[str, Any],
        *,
        now: datetime | None,
    ) -> None:
        participant_id = str(response_record["participant_id"])
        participant = self.latest_participants().get(participant_id)
        if not participant:
            return
        assigned_count = int(participant.get("assigned_video_count") or 0)
        completed_video_ids = {
            str(record["video_id"])
            for record in self.responses()
            if str(record.get("participant_id")) == participant_id
        }
        if assigned_count <= 0 or len(completed_video_ids) < assigned_count:
            return
        if participant.get("completion_status") == "completed":
            return
        timestamp = _timestamp(now)
        completed = dict(participant)
        completed["completion_status"] = "completed"
        completed["completed_at"] = timestamp
        completed["recorded_at"] = timestamp
        self._append_jsonl(self.participants_path, completed)

    def _append_jsonl(self, path: Path, record: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(dict(record), sort_keys=True) + "\n")


def _validate_answers(raw_answers: Any, *, include_q5: bool) -> dict[str, dict[str, Any]]:
    if not isinstance(raw_answers, Mapping):
        raise SurveyStorageError("answers must be an object")
    required_ids = {question.id for question in CORE_QUESTIONS}
    missing = sorted(required_ids - set(raw_answers))
    if missing:
        raise SurveyStorageError(f"missing required answers: {missing}")
    allowed = set(required_ids)
    if include_q5:
        allowed.add(OPTIONAL_Q5.id)
    unknown = sorted(set(raw_answers) - allowed)
    if unknown:
        raise SurveyStorageError(f"unknown answer ids: {unknown}")
    answers: dict[str, dict[str, Any]] = {}
    for question_id, raw_value in raw_answers.items():
        question = get_question(question_id, include_q5=include_q5)
        try:
            likert = int(raw_value)
            score = likert_to_score(likert)
        except (SurveyDesignError, TypeError, ValueError) as exc:
            raise SurveyStorageError(str(exc)) from exc
        answers[question_id] = {
            "likert": likert,
            "score_0_100": score,
            "axis_id": question.axis_id,
            "primary_score": question.primary_score,
        }
    return answers


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SurveyStorageError(f"invalid JSONL at {path}:{line_number}") from exc
        if not isinstance(payload, dict):
            raise SurveyStorageError(f"JSONL record must be an object at {path}:{line_number}")
        records.append(payload)
    return records


def _timestamp(now: datetime | None = None) -> str:
    value = now or datetime.now(tz=UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _participant_id() -> str:
    return f"p_{uuid4().hex[:12]}"

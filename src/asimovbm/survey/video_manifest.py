"""Survey video manifest loading and validation."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .survey_design import SurveyDesignError, get_study_cell


class VideoManifestError(ValueError):
    """Raised when a survey video manifest is invalid."""


@dataclass(frozen=True)
class SurveyVideo:
    video_id: str
    path: str
    policy_id: str
    viewpoint: str
    robot_id: str
    episode_id: str
    group_ids: tuple[str, ...]
    title: str = ""
    episode_order: int = 0
    metrics: dict[str, Any] = field(default_factory=dict)

    def resolved_path(self, video_root: Path) -> Path:
        return _safe_child(video_root, self.path)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["group_ids"] = list(self.group_ids)
        return payload


@dataclass(frozen=True)
class SurveyVideoManifest:
    study_id: str
    videos: tuple[SurveyVideo, ...]
    schema_version: str = "asimovbm.survey_video_manifest.v1"

    def videos_for_group(self, group_id: str) -> tuple[SurveyVideo, ...]:
        try:
            get_study_cell(group_id)
        except SurveyDesignError as exc:
            raise VideoManifestError(str(exc)) from exc
        selected = [video for video in self.videos if group_id in video.group_ids]
        return tuple(sorted(selected, key=lambda video: (video.episode_order, video.video_id)))

    def get_video(self, video_id: str) -> SurveyVideo:
        for video in self.videos:
            if video.video_id == video_id:
                return video
        raise VideoManifestError(f"unknown video id: {video_id}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "study_id": self.study_id,
            "videos": [video.to_dict() for video in self.videos],
        }


def load_video_manifest(path: Path | str, *, video_root: Path | str) -> SurveyVideoManifest:
    manifest_path = Path(path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    return parse_video_manifest(payload, video_root=Path(video_root))


def parse_video_manifest(
    payload: Mapping[str, Any],
    *,
    video_root: Path,
) -> SurveyVideoManifest:
    videos_payload = payload.get("videos", ())
    if not isinstance(videos_payload, Iterable):
        raise VideoManifestError("video manifest must contain a videos list")
    videos = tuple(_parse_video(video, video_root=video_root) for video in videos_payload)
    video_ids = [video.video_id for video in videos]
    if len(set(video_ids)) != len(video_ids):
        raise VideoManifestError("video ids must be unique")
    return SurveyVideoManifest(
        study_id=str(payload.get("study_id", "pilot")),
        schema_version=str(
            payload.get("schema_version", "asimovbm.survey_video_manifest.v1")
        ),
        videos=videos,
    )


def empty_video_manifest(study_id: str = "pilot") -> SurveyVideoManifest:
    return SurveyVideoManifest(study_id=study_id, videos=())


def _parse_video(payload: Any, *, video_root: Path) -> SurveyVideo:
    if not isinstance(payload, Mapping):
        raise VideoManifestError("each video entry must be an object")
    group_ids = tuple(str(group_id) for group_id in payload.get("group_ids", ()))
    if not group_ids:
        raise VideoManifestError("video entry must include at least one group id")
    for group_id in group_ids:
        try:
            get_study_cell(group_id)
        except SurveyDesignError as exc:
            raise VideoManifestError(str(exc)) from exc
    path = str(payload["path"])
    _safe_child(video_root, path)
    return SurveyVideo(
        video_id=str(payload["video_id"]),
        path=path,
        policy_id=str(payload["policy_id"]),
        viewpoint=str(payload["viewpoint"]),
        robot_id=str(payload.get("robot_id", "g1")),
        episode_id=str(payload["episode_id"]),
        group_ids=group_ids,
        title=str(payload.get("title", payload["video_id"])),
        episode_order=int(payload.get("episode_order", 0)),
        metrics=dict(payload.get("metrics", {})),
    )


def _safe_child(root: Path, child: str | Path) -> Path:
    root_resolved = root.resolve()
    candidate = Path(child)
    if not candidate.is_absolute():
        candidate = root_resolved / candidate
    candidate_resolved = candidate.resolve(strict=False)
    if candidate_resolved != root_resolved and root_resolved not in candidate_resolved.parents:
        raise VideoManifestError("video path must stay inside the configured video root")
    return candidate_resolved

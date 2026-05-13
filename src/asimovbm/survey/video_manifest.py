"""Survey video manifest loading and validation."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .survey_design import SurveyDesignError, get_study_cell

PREDICTION_SOURCE_KINDS: tuple[str, ...] = (
    "metrics_json",
    "episode_metrics_csv",
    "simulation_json",
)


class VideoManifestError(ValueError):
    """Raised when a survey video manifest is invalid."""


@dataclass(frozen=True)
class PredictionSource:
    kind: str
    path: str
    root: str = "artifact_root"
    run_id: str | None = None
    episode_id: str | None = None
    iteration: int | None = None
    row_selector: dict[str, Any] = field(default_factory=dict)


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
    prediction_source: PredictionSource | None = None

    def resolved_path(self, video_root: Path) -> Path:
        return _safe_child(video_root, self.path, label="video path")

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


def load_video_manifest(
    path: Path | str,
    *,
    video_root: Path | str,
    artifact_root: Path | str | None = None,
    prediction_roots: Mapping[str, Path | str] | None = None,
) -> SurveyVideoManifest:
    manifest_path = Path(path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    resolved_artifact_root = Path(artifact_root) if artifact_root is not None else manifest_path.parent
    return parse_video_manifest(
        payload,
        video_root=Path(video_root),
        artifact_root=resolved_artifact_root,
        prediction_roots=prediction_roots,
    )


def parse_video_manifest(
    payload: Mapping[str, Any],
    *,
    video_root: Path,
    artifact_root: Path | None = None,
    prediction_roots: Mapping[str, Path | str] | None = None,
) -> SurveyVideoManifest:
    videos_payload = payload.get("videos", ())
    if not isinstance(videos_payload, Iterable):
        raise VideoManifestError("video manifest must contain a videos list")
    roots = _prediction_roots(artifact_root or video_root, prediction_roots)
    videos = tuple(
        _parse_video(video, video_root=video_root, prediction_roots=roots)
        for video in videos_payload
    )
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


def discover_sim_output_manifest(
    *,
    study_id: str,
    video_root: Path | str,
    json_root: Path | str,
    include_go2: bool = False,
) -> SurveyVideoManifest:
    """Build a manifest from paired Unity video-generation outputs."""

    video_root = Path(video_root)
    json_root = Path(json_root)
    videos = tuple(
        _discover_sim_video(video_path, video_root=video_root, json_root=json_root)
        for video_path in sorted(video_root.rglob("*.mp4"))
        if _is_sim_output_video(video_path, video_root=video_root)
    )
    if not include_go2:
        videos = tuple(video for video in videos if video.robot_id != "go2")
    video_ids = [video.video_id for video in videos]
    if len(set(video_ids)) != len(video_ids):
        raise VideoManifestError("discovered video ids must be unique")
    return SurveyVideoManifest(study_id=study_id, videos=videos)


def _parse_video(
    payload: Any,
    *,
    video_root: Path,
    prediction_roots: Mapping[str, Path],
) -> SurveyVideo:
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
    _safe_child(video_root, path, label="video path")
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
        prediction_source=_parse_prediction_source(
            payload.get("prediction_source"),
            prediction_roots=prediction_roots,
        ),
    )


def _parse_prediction_source(
    value: Any,
    *,
    prediction_roots: Mapping[str, Path],
) -> PredictionSource | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise VideoManifestError("prediction_source must be an object")
    kind = str(value.get("kind", ""))
    if kind not in PREDICTION_SOURCE_KINDS:
        allowed = ", ".join(PREDICTION_SOURCE_KINDS)
        raise VideoManifestError(f"prediction_source kind must be one of {allowed}")
    path = str(value.get("path", ""))
    if not path:
        raise VideoManifestError("prediction_source path is required")
    root = str(value.get("root", "artifact_root"))
    if root not in prediction_roots:
        known_roots = ", ".join(sorted(prediction_roots))
        raise VideoManifestError(f"prediction_source root must be one of {known_roots}")
    _safe_child(prediction_roots[root], path, label="prediction source path")
    iteration = value.get("iteration")
    if iteration is not None:
        iteration = int(iteration)
    row_selector = value.get("row_selector", {})
    if row_selector is None:
        row_selector = {}
    if not isinstance(row_selector, Mapping):
        raise VideoManifestError("prediction_source row_selector must be an object")
    return PredictionSource(
        kind=kind,
        path=path,
        root=root,
        run_id=_optional_string(value.get("run_id")),
        episode_id=_optional_string(value.get("episode_id")),
        iteration=iteration,
        row_selector=dict(row_selector),
    )


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None


def _prediction_roots(
    artifact_root: Path,
    extra_roots: Mapping[str, Path | str] | None,
) -> dict[str, Path]:
    roots = {"artifact_root": Path(artifact_root)}
    if extra_roots:
        roots.update({str(name): Path(path) for name, path in extra_roots.items()})
    return roots


def _is_sim_output_video(video_path: Path, *, video_root: Path) -> bool:
    try:
        relative = video_path.relative_to(video_root)
    except ValueError:
        return False
    return len(relative.parts) == 3 and relative.suffix.lower() == ".mp4"


def _discover_sim_video(video_path: Path, *, video_root: Path, json_root: Path) -> SurveyVideo:
    relative = video_path.relative_to(video_root)
    policy_path, view_path, filename = relative.parts
    episode_from_path = Path(filename).stem
    sidecar_path = json_root / policy_path / view_path / f"{episode_from_path}.json"
    metadata = _read_sidecar_metadata(sidecar_path)
    policy_id = _normalized_id(_metadata_string(metadata, "policy_id") or policy_path)
    camera_view = _normalized_id(_metadata_string(metadata, "camera_view") or view_path)
    viewpoint, group_suffix = _survey_viewpoint(camera_view)
    episode_id = _metadata_string(metadata, "episode_id") or episode_from_path
    robot_id = _normalized_id(_metadata_string(metadata, "robot_id") or "g1")
    group_id = f"{policy_id}_{group_suffix}"
    if robot_id == "go2":
        group_id = f"go2_{group_id}"
    source = None
    if sidecar_path.exists():
        source = PredictionSource(
            kind="simulation_json",
            path=sidecar_path.relative_to(json_root).as_posix(),
            root="survey_json_root",
            episode_id=episode_id,
        )
    return SurveyVideo(
        video_id=_video_id(policy_id, group_suffix, episode_id, robot_id),
        path=relative.as_posix(),
        policy_id=policy_id,
        viewpoint=viewpoint,
        robot_id=robot_id,
        episode_id=episode_id,
        group_ids=(group_id,),
        title=_title(policy_id, camera_view, episode_id),
        episode_order=_episode_order(episode_id),
        metrics={"camera_view": camera_view, "json_sidecar_path": source.path if source else None},
        prediction_source=source,
    )


def _read_sidecar_metadata(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, Mapping) else {}


def _metadata_string(payload: Mapping[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None and isinstance(payload.get("metadata"), Mapping):
        value = payload["metadata"].get(key)
    if value is None and isinstance(payload.get("render"), Mapping):
        value = payload["render"].get(key)
    if value is None:
        return None
    text = str(value)
    return text or None


def _normalized_id(value: str) -> str:
    return value.strip().lower().replace("-", "_")


def _survey_viewpoint(camera_view: str) -> tuple[str, str]:
    if camera_view in {"arrival", "fp", "first_person", "firstperson"}:
        return "first_person", "fp"
    if camera_view == "bystander":
        return "bystander", "bystander"
    return camera_view, camera_view


def _video_id(policy_id: str, group_suffix: str, episode_id: str, robot_id: str) -> str:
    prefix = f"{robot_id}_" if robot_id != "g1" else ""
    return f"{prefix}{policy_id}_{group_suffix}_{episode_id}"


def _title(policy_id: str, camera_view: str, episode_id: str) -> str:
    return " - ".join(
        (
            _humanize(policy_id),
            _humanize(camera_view),
            _humanize(episode_id),
        )
    )


def _humanize(value: str) -> str:
    return value.replace("_", " ").strip().title()


def _episode_order(episode_id: str) -> int:
    if episode_id.endswith("approach_user") or episode_id.endswith("point_to_point_open"):
        return 1
    if episode_id.endswith("lateral_open") or episode_id.endswith("point_to_point_static_obstacles"):
        return 2
    if episode_id.endswith("lateral_static_dynamic_obstacles") or episode_id.endswith("point_to_point_dynamic_npcs"):
        return 3
    return 999


def _safe_child(root: Path, child: str | Path, *, label: str) -> Path:
    root_resolved = root.resolve()
    candidate = Path(child)
    if not candidate.is_absolute():
        candidate = root_resolved / candidate
    candidate_resolved = candidate.resolve(strict=False)
    if candidate_resolved != root_resolved and root_resolved not in candidate_resolved.parents:
        raise VideoManifestError(f"{label} must stay inside the configured root")
    return candidate_resolved

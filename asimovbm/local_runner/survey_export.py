"""Survey video export from MuJoCo episode recordings."""

from __future__ import annotations

import csv
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from g1_slam.mujoco_runner import DEFAULT_NAVIGATION_CONTROL_DT_S, record_mujoco_navigation_video

from asimovbm.metrics import SOCIAL_NAVIGATION_AXIS_IDS
from g1_slam.config import visualization_for_camera_view

from .artifacts import write_json
from .backends import _dynamic_obstacles, _episode_world, _viewer_locomotion_config
from .catalog import LocalEpisodeSpec
from .traces import LocalRunRecord

SURVEY_SCHEMA_VERSION = "asimovbm.simulation_episode.v1"
DEFAULT_SURVEY_VIEWS: tuple[str, ...] = ("arrival", "bystander")


class SurveyExportError(RuntimeError):
    """Raised when survey export cannot produce a complete folder."""


@dataclass(frozen=True)
class SurveyVideoExportConfig:
    survey_root: Path = Path("artifacts/survey")
    policy_id: str | None = None
    views: tuple[str, ...] = DEFAULT_SURVEY_VIEWS
    fps: int = 24
    width: int = 1280
    height: int = 720
    max_duration_s: float | None = 15.0

    @property
    def video_root(self) -> Path:
        return self.survey_root / "videos"

    @property
    def json_root(self) -> Path:
        return self.survey_root / "json"

    def validate(self) -> None:
        if self.fps < 1:
            raise ValueError("survey video fps must be >= 1")
        if self.width < 320 or self.height < 240:
            raise ValueError("survey video dimensions must be at least 320x240")
        if self.max_duration_s is not None and self.max_duration_s <= 0.0:
            raise ValueError("survey video max duration must be > 0")
        unknown_views = sorted(set(self.views) - set(DEFAULT_SURVEY_VIEWS))
        if unknown_views:
            raise ValueError(f"survey video views must be arrival/bystander, got {unknown_views}")


@dataclass(frozen=True)
class SurveyVideoExport:
    policy_id: str
    view: str
    episode_id: str
    video_path: Path
    json_path: Path

    def to_summary_row(self, root: Path) -> dict[str, str]:
        return {
            "policy_id": self.policy_id,
            "camera_view": self.view,
            "episode_id": self.episode_id,
            "video_path": self.video_path.relative_to(root).as_posix(),
            "json_path": self.json_path.relative_to(root).as_posix(),
        }


@dataclass(frozen=True)
class SurveyExportResult:
    survey_root: Path
    video_root: Path
    json_root: Path
    summary_json_path: Path
    summary_csv_path: Path
    videos: tuple[SurveyVideoExport, ...]

    def to_manifest_entry(self, run_dir: Path | None = None) -> dict[str, Any]:
        def path_text(path: Path) -> str:
            if run_dir is None:
                return path.as_posix()
            try:
                return path.relative_to(run_dir).as_posix()
            except ValueError:
                return path.as_posix()

        return {
            "survey_root": self.survey_root.as_posix(),
            "video_root": self.video_root.as_posix(),
            "json_root": self.json_root.as_posix(),
            "summary_json_path": path_text(self.summary_json_path),
            "summary_csv_path": path_text(self.summary_csv_path),
            "videos": [
                {
                    "policy_id": item.policy_id,
                    "camera_view": item.view,
                    "episode_id": item.episode_id,
                    "video_path": item.video_path.as_posix(),
                    "json_path": item.json_path.as_posix(),
                }
                for item in self.videos
            ],
        }


def export_survey_videos(
    *,
    run_id: str,
    specs_by_id: dict[str, LocalEpisodeSpec],
    records: list[LocalRunRecord],
    config: SurveyVideoExportConfig,
) -> SurveyExportResult:
    """Render MuJoCo videos and sidecars following the survey folder contract."""

    config.validate()
    if not records:
        raise SurveyExportError("cannot export survey videos for an empty run")

    _require_video_dependencies()
    config.video_root.mkdir(parents=True, exist_ok=True)
    config.json_root.mkdir(parents=True, exist_ok=True)

    exports: list[SurveyVideoExport] = []
    for record in records:
        spec = specs_by_id.get(record.trace.episode_id)
        if spec is None:
            raise SurveyExportError(f"missing episode spec for trace {record.trace.episode_id}")
        policy_id = _survey_policy_id(config.policy_id or spec.policy_id)
        episode_id = _survey_episode_id(spec.id)
        for view in config.views:
            video_path = config.video_root / policy_id / view / f"{episode_id}.mp4"
            json_path = config.json_root / policy_id / view / f"{episode_id}.json"
            video_path.parent.mkdir(parents=True, exist_ok=True)
            json_path.parent.mkdir(parents=True, exist_ok=True)
            print(
                f"rendering survey video: {record.trace.episode_id} / {view} -> {video_path}",
                file=sys.stderr,
                flush=True,
            )
            _render_mujoco_video(record, spec, view=view, output_path=video_path, config=config)
            write_json(
                json_path,
                _sidecar_payload(
                    run_id=run_id,
                    record=record,
                    spec=spec,
                    policy_id=policy_id,
                    episode_id=episode_id,
                    camera_view=view,
                    video_path=video_path,
                    config=config,
                ),
            )
            exports.append(
                SurveyVideoExport(
                    policy_id=policy_id,
                    view=view,
                    episode_id=episode_id,
                    video_path=video_path,
                    json_path=json_path,
                )
            )

    _validate_exports(exports, video_root=config.video_root, json_root=config.json_root)
    summary_json_path = config.survey_root / f"metrics-summary-{run_id}.json"
    summary_csv_path = config.survey_root / f"metrics-summary-{run_id}.csv"
    _write_summary(run_id, records, exports, summary_json_path, summary_csv_path, config.survey_root)
    return SurveyExportResult(
        survey_root=config.survey_root,
        video_root=config.video_root,
        json_root=config.json_root,
        summary_json_path=summary_json_path,
        summary_csv_path=summary_csv_path,
        videos=tuple(exports),
    )


def _render_mujoco_video(
    record: LocalRunRecord,
    spec: LocalEpisodeSpec,
    *,
    view: str,
    output_path: Path,
    config: SurveyVideoExportConfig,
) -> None:
    try:
        visualization = visualization_for_camera_view(spec.config.visualization, camera_view=view)
    except ValueError as exc:
        raise SurveyExportError(str(exc)) from exc
    try:
        record_mujoco_navigation_video(
            _episode_world(spec),
            robot=spec.robot_selector,
            model_path=None,
            start=spec.config.start,
            goal=spec.config.goal,
            steps=spec.config.steps,
            controller_config=spec.config.controller,
            locomotion_config=_viewer_locomotion_config(spec),
            output_path=output_path,
            visualization_config=visualization,
            dynamic_obstacles=_dynamic_obstacles(spec),
            fps=config.fps,
            width=config.width,
            height=config.height,
            control_dt_s=DEFAULT_NAVIGATION_CONTROL_DT_S,
            max_duration_s=config.max_duration_s,
        )
    except Exception as exc:
        raise SurveyExportError(
            f"failed to render MuJoCo survey video for {record.trace.episode_id}/{view}: {exc}"
        ) from exc


def _sidecar_payload(
    *,
    run_id: str,
    record: LocalRunRecord,
    spec: LocalEpisodeSpec,
    policy_id: str,
    episode_id: str,
    camera_view: str,
    video_path: Path,
    config: SurveyVideoExportConfig,
) -> dict[str, Any]:
    return {
        "schema_version": SURVEY_SCHEMA_VERSION,
        "run_id": run_id,
        "episode_id": episode_id,
        "source_episode_id": spec.id,
        "robot_id": spec.robot_id,
        "policy_id": policy_id,
        "camera_view": camera_view,
        "video_path": video_path.as_posix(),
        "render_backend": {
            "kind": "mujoco_offscreen",
            "robot_selector": spec.robot_selector,
            "locomotion_mode": _viewer_locomotion_config(spec).mode,
            "control_dt_s": DEFAULT_NAVIGATION_CONTROL_DT_S,
            "fps": config.fps,
            "width": config.width,
            "height": config.height,
            "max_duration_s": config.max_duration_s,
            "container": "mp4",
            "video_codec": "h264",
            "pixel_format": "yuv420p",
        },
        "metric_report": record.metrics,
        "metadata": {
            "iteration": record.trace.iteration,
            "terminal_status": record.trace.terminal_status,
            "technical_valid": record.trace.technical_valid,
            "trace_path": record.trace_path,
            "metrics_path": record.metrics_path,
        },
    }


def _write_summary(
    run_id: str,
    records: list[LocalRunRecord],
    exports: list[SurveyVideoExport],
    json_path: Path,
    csv_path: Path,
    survey_root: Path,
) -> None:
    export_rows = [export.to_summary_row(survey_root) for export in exports]
    write_json(
        json_path,
        {
            "schema_version": "asimovbm.survey_export_summary.v1",
            "run_id": run_id,
            "video_count": len(exports),
            "episodes": [
                {
                    "episode_id": record.trace.episode_id,
                    "iteration": record.trace.iteration,
                    "metric_report": record.metrics,
                }
                for record in records
            ],
            "videos": export_rows,
        },
    )
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = ["policy_id", "camera_view", "episode_id", "video_path", "json_path", *SOCIAL_NAVIGATION_AXIS_IDS]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        metrics_by_episode = {
            _survey_episode_id(record.trace.episode_id): record.metrics for record in records
        }
        for export in exports:
            axes = metrics_by_episode.get(export.episode_id, {}).get("behavioral_metrics", {}).get("axes", {})
            writer.writerow(
                {
                    **export.to_summary_row(survey_root),
                    **{
                        axis_id: axes.get(axis_id, {}).get("score")
                        for axis_id in SOCIAL_NAVIGATION_AXIS_IDS
                    },
                }
            )


def _validate_exports(exports: list[SurveyVideoExport], *, video_root: Path, json_root: Path) -> None:
    if not exports:
        raise SurveyExportError("survey export produced no videos")
    for export in exports:
        video_rel = export.video_path.relative_to(video_root)
        json_rel = export.json_path.relative_to(json_root)
        if len(video_rel.parts) != 3 or len(json_rel.parts) != 3:
            raise SurveyExportError(f"survey export paths must be <policy>/<view>/<episode>: {video_rel}")
        if video_rel.with_suffix("") != json_rel.with_suffix(""):
            raise SurveyExportError(f"survey video/json stems do not match: {video_rel} vs {json_rel}")
        if not export.video_path.exists() or export.video_path.stat().st_size <= 0:
            raise SurveyExportError(f"missing exported video: {export.video_path}")
        if not export.json_path.exists():
            raise SurveyExportError(f"missing JSON sidecar: {export.json_path}")
        payload = _read_json(export.json_path)
        _validate_sidecar(payload, export=export, relative=json_rel)


def _validate_sidecar(payload: dict[str, Any], *, export: SurveyVideoExport, relative: Path) -> None:
    policy, view, filename = relative.parts
    episode = Path(filename).stem
    if payload.get("policy_id") != policy or policy != export.policy_id:
        raise SurveyExportError(f"policy_id mismatch in {export.json_path}")
    if payload.get("camera_view") != view or view != export.view:
        raise SurveyExportError(f"camera_view mismatch in {export.json_path}")
    if payload.get("episode_id") != episode or episode != export.episode_id:
        raise SurveyExportError(f"episode_id mismatch in {export.json_path}")
    if not payload.get("robot_id"):
        raise SurveyExportError(f"robot_id missing in {export.json_path}")
    axes = payload.get("metric_report", {}).get("behavioral_metrics", {}).get("axes", {})
    missing_axes = [axis_id for axis_id in SOCIAL_NAVIGATION_AXIS_IDS if axis_id not in axes]
    if missing_axes:
        raise SurveyExportError(f"metric axes missing in {export.json_path}: {missing_axes}")


def _read_json(path: Path) -> dict[str, Any]:
    import json

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SurveyExportError(f"JSON sidecar must be an object: {path}")
    return payload


def _survey_policy_id(policy_id: str) -> str:
    return policy_id.strip().lower().replace("-", "_")


def _survey_episode_id(episode_id: str) -> str:
    return episode_id.strip().lower().replace("-", "_")


def _require_video_dependencies() -> None:
    if shutil.which("ffmpeg") is None:
        raise SurveyExportError("ffmpeg is required to export survey MP4 videos")
    os.environ.setdefault("MUJOCO_GL", "egl")
    try:
        import mujoco  # noqa: F401
    except ModuleNotFoundError as exc:
        raise SurveyExportError(
            "survey video export requires mujoco in the repo .venv"
        ) from exc


def _tail(value: bytes, limit: int = 800) -> str:
    return value.decode("utf-8", errors="replace")[-limit:]

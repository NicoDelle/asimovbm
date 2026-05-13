"""Load objective episode predictions referenced by survey videos."""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

from asimovbm.metrics import SOCIAL_NAVIGATION_METRIC_IDS

from .survey_design import SURVEY_AXIS_IDS
from .video_manifest import PredictionSource, SurveyVideo

PREDICTION_SCHEMA_VERSION = "asimovbm.survey_prediction.v1"


def load_video_predictions(
    videos: Sequence[SurveyVideo],
    *,
    artifact_root: Path,
    source_roots: Mapping[str, Path] | None = None,
) -> dict[str, dict[str, Any]]:
    return {
        video.video_id: load_video_prediction(
            video,
            artifact_root=artifact_root,
            source_roots=source_roots,
        )
        for video in videos
    }


def load_video_prediction(
    video: SurveyVideo,
    *,
    artifact_root: Path,
    source_roots: Mapping[str, Path] | None = None,
) -> dict[str, Any]:
    if video.prediction_source is None:
        return _inline_metrics_prediction(video)
    source = video.prediction_source
    root = _source_root(source, artifact_root=artifact_root, source_roots=source_roots)
    try:
        if source.kind == "metrics_json":
            return _prediction_from_metrics_json(video, source, root)
        if source.kind == "episode_metrics_csv":
            return _prediction_from_episode_metrics_csv(video, source, root)
        if source.kind == "simulation_json":
            return _prediction_from_simulation_json(video, source, root)
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
        return _empty_prediction(
            video,
            status="source_error",
            source=source,
            diagnostics=[{"reason": str(exc)}],
        )
    return _empty_prediction(
        video,
        status="unsupported_source",
        source=source,
        diagnostics=[{"reason": f"unsupported prediction source kind: {source.kind}"}],
    )


def _prediction_from_metrics_json(
    video: SurveyVideo,
    source: PredictionSource,
    root: Path,
) -> dict[str, Any]:
    path = _safe_child(root, source.path)
    payload = _load_json(path)
    metric_report = _metric_report_from_payload(payload)
    if metric_report is None:
        return _empty_prediction(
            video,
            status="unsupported_source",
            source=source,
            diagnostics=[{"reason": "metrics_json did not contain a metric report"}],
        )
    return _prediction_from_metric_report(video, metric_report, source=source)


def _prediction_from_episode_metrics_csv(
    video: SurveyVideo,
    source: PredictionSource,
    root: Path,
) -> dict[str, Any]:
    path = _safe_child(root, source.path)
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    row, diagnostics = _select_csv_row(rows, video=video, source=source)
    if row is None:
        return _empty_prediction(video, status="missing_row", source=source, diagnostics=diagnostics)
    axes = {
        axis_id: {"score": _scale_score(_parse_number(row.get(axis_id))), "status": "computed"}
        for axis_id in SURVEY_AXIS_IDS
    }
    features = {
        metric_id: {
            "score": _scale_score(_parse_number(row.get(metric_id))),
            "status": "computed" if row.get(metric_id) not in (None, "") else "missing",
        }
        for metric_id in SOCIAL_NAVIGATION_METRIC_IDS
    }
    return _prediction_payload(
        video,
        status="computed" if _has_any_score(axes) else "empty_source",
        source=source,
        axes=axes,
        features=features,
        diagnostics=diagnostics,
    )


def _prediction_from_simulation_json(
    video: SurveyVideo,
    source: PredictionSource,
    root: Path,
) -> dict[str, Any]:
    path = _safe_child(root, source.path)
    payload = _load_json(path)
    metric_report = _metric_report_from_payload(payload)
    if metric_report is not None:
        return _prediction_from_metric_report(video, metric_report, source=source)
    metric_report = _metric_report_from_trace_payload(payload)
    if metric_report is not None:
        return _prediction_from_metric_report(video, metric_report, source=source)
    return _empty_prediction(
        video,
        status="unsupported_source",
        source=source,
        diagnostics=[{"reason": "simulation_json schema could not be converted to metrics"}],
    )


def _metric_report_from_payload(payload: Mapping[str, Any]) -> Mapping[str, Any] | None:
    if isinstance(payload.get("behavioral_metrics"), Mapping):
        return payload
    metric_report = payload.get("metric_report")
    if isinstance(metric_report, Mapping):
        return metric_report
    prediction = payload.get("prediction")
    if isinstance(prediction, Mapping):
        return _metric_report_from_payload(prediction)
    metrics = payload.get("metrics")
    if isinstance(metrics, Mapping) and isinstance(metrics.get("behavioral_metrics"), Mapping):
        return metrics
    return None


def _metric_report_from_trace_payload(payload: Mapping[str, Any]) -> Mapping[str, Any] | None:
    try:
        for key in ("trace", "replay", "simulation_trace", "unity_trace"):
            nested = payload.get(key)
            if isinstance(nested, Mapping):
                report = _metric_report_from_trace_payload(
                    _trace_payload_with_parent_context(payload, nested)
                )
                if report is not None:
                    return report
        if payload.get("schema_version") == "asimovbm.unity_trace.v1":
            from asimovbm.local_runner.metrics_bridge import build_trace_metric_report
            from asimovbm.local_runner.unity_ingest import unity_payload_to_trace

            return build_trace_metric_report(unity_payload_to_trace(dict(payload)))
        if "steps" in payload and "episode_id" in payload:
            from asimovbm.local_runner.metrics_bridge import build_trace_metric_report
            from asimovbm.local_runner.traces import LocalEpisodeTrace, LocalStepTrace

            steps = tuple(
                LocalStepTrace(
                    step_id=int(step["step_id"]),
                    time_s=float(step["time_s"]),
                    dt_s=float(step["dt_s"]),
                    robot_pose=_number_tuple(step.get("robot_pose"), 3),
                    robot_velocity=_number_tuple(step.get("robot_velocity"), 3),
                    action=_number_tuple(step.get("action", (0.0, 0.0)), 2),
                    distance_to_goal=float(step["distance_to_goal"]),
                    lidar_ranges=_number_tuple(step.get("lidar_ranges", ())),
                    static_entities=_dict_tuple(step.get("static_entities")),
                    dynamic_entities=_dict_tuple(step.get("dynamic_entities")),
                    collisions=_dict_tuple(step.get("collisions")),
                    social_cues=_dict_tuple(step.get("social_cues")),
                    public_observation=dict(step.get("public_observation") or {}),
                    qpos=_number_tuple(step.get("qpos", ())),
                    qvel=_number_tuple(step.get("qvel", ())),
                    status=str(step.get("status", "running")),
                    metadata=dict(step.get("metadata") or {}),
                )
                for step in _list(payload.get("steps"))
            )
            return build_trace_metric_report(
                LocalEpisodeTrace(
                    episode_id=str(payload["episode_id"]),
                    iteration=int(payload.get("iteration", 0)),
                    tier_id=str(payload.get("tier_id", "local_validation")),
                    technical_valid=bool(payload.get("technical_valid", True)),
                    terminal_status=str(payload.get("terminal_status", "timeout")),
                    steps=steps,
                    config_checksum_sha256=str(payload.get("config_checksum_sha256", "")),
                    config_path=str(payload.get("config_path", "")),
                    robot_selector=str(payload.get("robot_selector", "")),
                    canonical_backend_id=str(payload.get("canonical_backend_id", "")),
                    execution_backend_id=str(payload.get("execution_backend_id", "")),
                    viewer_mode=str(payload.get("viewer_mode", "headless")),
                    metadata=_metadata(payload.get("metadata")),
                )
            )
    except (KeyError, TypeError, ValueError):
        return None
    return None


def _prediction_from_metric_report(
    video: SurveyVideo,
    metric_report: Mapping[str, Any],
    *,
    source: PredictionSource | None,
) -> dict[str, Any]:
    behavioral = _mapping(metric_report.get("behavioral_metrics"))
    axis_payload = _mapping(behavioral.get("axes"))
    axes = {
        axis_id: _axis_prediction(axis_payload.get(axis_id))
        for axis_id in SURVEY_AXIS_IDS
    }
    features_payload = _mapping(metric_report.get("metrics"))
    features = {
        metric_id: _feature_prediction(features_payload.get(metric_id))
        for metric_id in SOCIAL_NAVIGATION_METRIC_IDS
    }
    return _prediction_payload(
        video,
        status="computed" if _has_any_score(axes) else "empty_source",
        source=source,
        axes=axes,
        features=features,
        diagnostics=(),
    )


def _inline_metrics_prediction(video: SurveyVideo) -> dict[str, Any]:
    raw_axes = video.metrics.get("axes") or video.metrics.get("prediction_axes")
    if not isinstance(raw_axes, Mapping):
        return _empty_prediction(
            video,
            status="missing_source",
            source=None,
            diagnostics=[{"reason": "video has no prediction_source"}],
        )
    axes = {
        axis_id: _axis_prediction(raw_axes.get(axis_id))
        for axis_id in SURVEY_AXIS_IDS
    }
    return _prediction_payload(
        video,
        status="computed" if _has_any_score(axes) else "empty_source",
        source=None,
        axes=axes,
        features={},
        diagnostics=(),
    )


def _axis_prediction(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        score = _scale_score(_parse_number(value.get("score", value.get("mean"))))
        status = str(value.get("status", "computed" if score is not None else "missing"))
        return {"score": score, "status": status}
    score = _scale_score(_parse_number(value))
    return {"score": score, "status": "computed" if score is not None else "missing"}


def _feature_prediction(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        score = _scale_score(_parse_number(value.get("normalized_score", value.get("score"))))
        status = str(value.get("status", "computed" if score is not None else "missing"))
        return {"score": score, "status": status}
    score = _scale_score(_parse_number(value))
    return {"score": score, "status": "computed" if score is not None else "missing"}


def _select_csv_row(
    rows: Sequence[Mapping[str, str]],
    *,
    video: SurveyVideo,
    source: PredictionSource,
) -> tuple[Mapping[str, str] | None, list[dict[str, Any]]]:
    selectors: dict[str, str] = {"episode_id": source.episode_id or video.episode_id}
    if source.run_id is not None:
        selectors["run_id"] = source.run_id
    if source.iteration is not None:
        selectors["iteration"] = str(source.iteration)
    selectors.update({str(key): str(value) for key, value in source.row_selector.items()})
    matches = [
        row
        for row in rows
        if all(str(row.get(key, "")) == value for key, value in selectors.items())
    ]
    if len(matches) == 1:
        return matches[0], []
    if not matches:
        return None, [{"reason": "no CSV row matched selectors", "selectors": selectors}]
    return None, [{"reason": "multiple CSV rows matched selectors", "selectors": selectors, "count": len(matches)}]


def _prediction_payload(
    video: SurveyVideo,
    *,
    status: str,
    source: PredictionSource | None,
    axes: Mapping[str, Any],
    features: Mapping[str, Any],
    diagnostics: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": PREDICTION_SCHEMA_VERSION,
        "status": status,
        "video_id": video.video_id,
        "policy_id": video.policy_id,
        "viewpoint": video.viewpoint,
        "robot_id": video.robot_id,
        "episode_id": video.episode_id,
        "source": asdict(source) if source is not None else None,
        "axes": {axis_id: dict(axes.get(axis_id, {"score": None, "status": "missing"})) for axis_id in SURVEY_AXIS_IDS},
        "features": {metric_id: dict(features.get(metric_id, {"score": None, "status": "missing"})) for metric_id in SOCIAL_NAVIGATION_METRIC_IDS},
        "diagnostics": [dict(diagnostic) for diagnostic in diagnostics],
    }


def _empty_prediction(
    video: SurveyVideo,
    *,
    status: str,
    source: PredictionSource | None,
    diagnostics: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return _prediction_payload(
        video,
        status=status,
        source=source,
        axes={},
        features={},
        diagnostics=diagnostics,
    )


def _source_root(
    source: PredictionSource,
    *,
    artifact_root: Path,
    source_roots: Mapping[str, Path] | None,
) -> Path:
    roots = {"artifact_root": artifact_root}
    if source_roots:
        roots.update({str(name): Path(path) for name, path in source_roots.items()})
    if source.root not in roots:
        known_roots = ", ".join(sorted(roots))
        raise ValueError(f"unknown prediction source root {source.root}; expected one of {known_roots}")
    return roots[source.root]


def _safe_child(root: Path, child: str | Path) -> Path:
    root_resolved = root.resolve()
    candidate = Path(child)
    if not candidate.is_absolute():
        candidate = root_resolved / candidate
    candidate_resolved = candidate.resolve(strict=False)
    if candidate_resolved != root_resolved and root_resolved not in candidate_resolved.parents:
        raise ValueError("prediction source path escapes artifact root")
    return candidate_resolved


def _load_json(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("prediction source JSON must be an object")
    return payload


def _trace_payload_with_parent_context(
    parent: Mapping[str, Any],
    child: Mapping[str, Any],
) -> dict[str, Any]:
    payload = dict(child)
    for key in (
        "episode_id",
        "iteration",
        "tier_id",
        "technical_valid",
        "terminal_status",
        "config_checksum_sha256",
        "config_path",
        "robot_selector",
        "canonical_backend_id",
        "execution_backend_id",
        "viewer_mode",
    ):
        if key not in payload and key in parent:
            payload[key] = parent[key]
    metadata = _metadata(parent.get("metadata"))
    metadata.update(_metadata(child.get("metadata")))
    for key in ("robot_id", "policy_id", "camera_view", "viewpoint"):
        if key in parent and key not in metadata:
            metadata[key] = parent[key]
    if metadata:
        payload["metadata"] = metadata
    return payload


def _scale_score(value: float | None) -> float | None:
    if value is None:
        return None
    if 0.0 <= value <= 1.0:
        return value * 100.0
    return value


def _parse_number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _has_any_score(axes: Mapping[str, Any]) -> bool:
    return any(isinstance(axis, Mapping) and axis.get("score") is not None for axis in axes.values())


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _number_tuple(value: Any, length: int | None = None) -> tuple[float, ...]:
    if value is None:
        value = ()
    if not isinstance(value, list | tuple):
        raise ValueError("trace numeric vector must be an array")
    result = tuple(float(item) for item in value)
    if length is not None and len(result) != length:
        raise ValueError("trace numeric vector has unexpected length")
    return result


def _dict_tuple(value: Any) -> tuple[dict[str, Any], ...]:
    if value is None:
        return ()
    if not isinstance(value, list | tuple):
        raise ValueError("trace object vector must be an array")
    return tuple(dict(item) for item in value if isinstance(item, Mapping))


def _list(value: Any) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError("trace steps must be an array")
    return value


def _metadata(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    metadata = dict(value)
    for key in ("start", "goal"):
        if isinstance(metadata.get(key), list):
            metadata[key] = tuple(metadata[key])
    return metadata

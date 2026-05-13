"""Ingest Unity-emitted traces into local validation artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from asimovbm.reports import JsonReportInput, build_json_report

from .artifacts import prepare_run_dir, relative_to_run, write_json
from .metrics_bridge import build_trace_metric_report
from .traces import LocalEpisodeTrace, LocalRunRecord, LocalStepTrace


UNITY_TRACE_SCHEMA_VERSION = "asimovbm.unity_trace.v1"
UNITY_VALIDATION_SCHEMA_VERSION = "asimovbm.unity_validation.v1"


class UnityTraceIngestError(RuntimeError):
    """Raised when a Unity trace cannot be safely converted."""


@dataclass(frozen=True)
class UnityIngestConfig:
    artifact_root: Path = Path("artifacts/unity-validation")
    run_id: str | None = None
    viewer_mode: str = "unity"
    extra_metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class UnityIngestResult:
    run_id: str
    run_dir: Path
    manifest_path: Path
    report_path: Path
    records: tuple[LocalRunRecord, ...]


def ingest_unity_trace_file(
    trace_path: Path,
    *,
    config: UnityIngestConfig | None = None,
) -> UnityIngestResult:
    return ingest_unity_trace_files((trace_path,), config=config)


def ingest_unity_trace_files(
    trace_paths: tuple[Path, ...] | list[Path],
    *,
    config: UnityIngestConfig | None = None,
) -> UnityIngestResult:
    config = config or UnityIngestConfig()
    if not trace_paths:
        raise UnityTraceIngestError("at least one Unity trace path is required")

    run_id = config.run_id or _new_run_id()
    paths = prepare_run_dir(config.artifact_root, run_id)
    records: list[LocalRunRecord] = []

    for index, raw_path in enumerate(trace_paths):
        payload = _load_json(raw_path)
        trace = unity_payload_to_trace(
            payload,
            default_iteration=index,
            default_viewer_mode=config.viewer_mode,
        )
        episode_dir = paths.run_dir / trace.episode_id / f"iteration-{trace.iteration:03d}"
        trace_output_path = episode_dir / "trace.json"
        metrics_output_path = episode_dir / "metrics.json"
        metric_report = build_trace_metric_report(trace)
        write_json(trace_output_path, trace.to_dict())
        write_json(metrics_output_path, metric_report)
        records.append(
            LocalRunRecord(
                trace=trace,
                metrics=metric_report,
                trace_path=relative_to_run(trace_output_path, paths.run_dir),
                metrics_path=relative_to_run(metrics_output_path, paths.run_dir),
            )
        )

    report_path = paths.run_dir / "report.json"
    write_json(report_path, _build_run_report(run_id, records))
    manifest = _build_manifest(
        run_id=run_id,
        records=records,
        report_path=relative_to_run(report_path, paths.run_dir),
        trace_paths=tuple(Path(path) for path in trace_paths),
        metadata=config.extra_metadata or {},
    )
    write_json(paths.manifest_path, manifest)
    return UnityIngestResult(
        run_id=run_id,
        run_dir=paths.run_dir,
        manifest_path=paths.manifest_path,
        report_path=report_path,
        records=tuple(records),
    )


def unity_payload_to_trace(
    payload: dict[str, Any],
    *,
    default_iteration: int = 0,
    default_viewer_mode: str = "unity",
) -> LocalEpisodeTrace:
    if not isinstance(payload, dict):
        raise UnityTraceIngestError("Unity trace payload must be a JSON object")
    schema_version = payload.get("schema_version")
    if schema_version not in (UNITY_TRACE_SCHEMA_VERSION, None):
        raise UnityTraceIngestError(f"unsupported Unity trace schema_version: {schema_version}")

    steps_payload = payload.get("steps")
    if not isinstance(steps_payload, list):
        raise UnityTraceIngestError("Unity trace payload must include a steps array")

    scene_id = _string(payload, "scene_id", fallback="unity_scene")
    episode_id = _string(payload, "episode_id", fallback=scene_id)
    metadata = _metadata(payload.get("metadata"))
    metadata.setdefault("unity_scene_id", scene_id)
    metadata.setdefault("unity_trace_schema_version", schema_version or UNITY_TRACE_SCHEMA_VERSION)
    if "movement_proof" in payload:
        metadata["movement_proof"] = payload["movement_proof"]

    steps = tuple(_step_from_payload(step, index) for index, step in enumerate(steps_payload))
    if not steps and payload.get("technical_valid", True):
        raise UnityTraceIngestError("technically valid Unity traces must include at least one step")

    technical_valid = bool(payload.get("technical_valid", True))
    terminal_status = _string(
        payload,
        "terminal_status",
        fallback="episode_failure" if not technical_valid else _terminal_status_from_steps(steps),
    )

    return LocalEpisodeTrace(
        episode_id=episode_id,
        iteration=_integer(payload, "iteration", fallback=default_iteration),
        tier_id=_string(payload, "tier_id", fallback="unity_validation"),
        technical_valid=technical_valid,
        terminal_status=terminal_status,
        steps=steps,
        config_checksum_sha256=_string(payload, "config_checksum_sha256", fallback="unity_trace"),
        config_path=_string(payload, "config_path", fallback="Assets/AsimovBM/MuJoCo/SceneManifest.json"),
        robot_selector=_string(payload, "robot_selector", fallback="unity_mujoco"),
        canonical_backend_id=_string(payload, "canonical_backend_id", fallback="unity_mujoco"),
        execution_backend_id=_string(payload, "execution_backend_id", fallback="unity_mujoco_trace_v1"),
        viewer_mode=_string(payload, "viewer_mode", fallback=default_viewer_mode),
        metadata=metadata,
    )


def _step_from_payload(payload: Any, fallback_step_id: int) -> LocalStepTrace:
    if not isinstance(payload, dict):
        raise UnityTraceIngestError(f"Unity step {fallback_step_id} must be a JSON object")
    return LocalStepTrace(
        step_id=_integer(payload, "step_id", fallback=fallback_step_id),
        time_s=_number(payload, "time_s"),
        dt_s=_number(payload, "dt_s"),
        robot_pose=_number_tuple(payload, "robot_pose", length=3),
        robot_velocity=_number_tuple(payload, "robot_velocity", length=3),
        action=_number_tuple(payload, "action", length=2, fallback=(0.0, 0.0)),
        distance_to_goal=_number(payload, "distance_to_goal", fallback=0.0),
        lidar_ranges=_number_tuple(payload, "lidar_ranges", fallback=()),
        static_entities=_dict_tuple(payload.get("static_entities")),
        dynamic_entities=_dict_tuple(payload.get("dynamic_entities")),
        collisions=_dict_tuple(payload.get("collisions")),
        social_cues=_dict_tuple(payload.get("social_cues")),
        public_observation=_dict(payload.get("public_observation")),
        qpos=_number_tuple(payload, "qpos", fallback=()),
        qvel=_number_tuple(payload, "qvel", fallback=()),
        status=_string(payload, "status", fallback="running"),
        metadata=_metadata(payload.get("metadata")),
    )


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise UnityTraceIngestError(f"could not read Unity trace {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise UnityTraceIngestError(f"could not parse Unity trace {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise UnityTraceIngestError(f"Unity trace {path} must contain a JSON object")
    return payload


def _build_run_report(run_id: str, records: list[LocalRunRecord]) -> dict[str, Any]:
    reliability = {
        "total_episode_runs": len(records),
        "technical_valid_episode_runs": sum(1 for record in records if record.trace.technical_valid),
        "technical_failures": sum(1 for record in records if not record.trace.technical_valid),
        "source": "unity",
    }
    return build_json_report(
        JsonReportInput(
            run_id=run_id,
            maturity="unity_mujoco_validation",
            reliability=reliability,
            behavioral_metrics={
                "status": "per_episode",
                "episode_blocks": [record.metrics["behavioral_metrics"] for record in records],
            },
        )
    )


def _build_manifest(
    *,
    run_id: str,
    records: list[LocalRunRecord],
    report_path: str,
    trace_paths: tuple[Path, ...],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": UNITY_VALIDATION_SCHEMA_VERSION,
        "run_id": run_id,
        "created_at": datetime.now(tz=UTC).isoformat(),
        "viewer_mode": "unity",
        "selected_episode_ids": tuple(record.trace.episode_id for record in records),
        "report_path": report_path,
        "records": [record.to_manifest_entry() for record in records],
        "raw_unity_traces": [str(path) for path in trace_paths],
        "metadata": dict(metadata),
    }


def _terminal_status_from_steps(steps: tuple[LocalStepTrace, ...]) -> str:
    if not steps:
        return "episode_failure"
    status = steps[-1].status
    return status if status != "running" else "timeout"


def _metadata(value: Any) -> dict[str, Any]:
    metadata = _dict(value)
    for key in ("start", "goal"):
        if key in metadata and isinstance(metadata[key], list):
            metadata[key] = tuple(metadata[key])
    return metadata


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _dict_tuple(value: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(dict(item) for item in value if isinstance(item, dict))


def _string(payload: dict[str, Any], key: str, *, fallback: str) -> str:
    value = payload.get(key, fallback)
    return str(value) if value is not None else fallback


def _integer(payload: dict[str, Any], key: str, *, fallback: int) -> int:
    value = payload.get(key, fallback)
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise UnityTraceIngestError(f"{key} must be an integer") from exc


def _number(payload: dict[str, Any], key: str, *, fallback: float | None = None) -> float:
    if key not in payload:
        if fallback is None:
            raise UnityTraceIngestError(f"{key} is required")
        return fallback
    try:
        return float(payload[key])
    except (TypeError, ValueError) as exc:
        raise UnityTraceIngestError(f"{key} must be a number") from exc


def _number_tuple(
    payload: dict[str, Any],
    key: str,
    *,
    length: int | None = None,
    fallback: tuple[float, ...] | None = None,
) -> tuple[float, ...]:
    if key not in payload:
        if fallback is None:
            raise UnityTraceIngestError(f"{key} is required")
        return fallback
    value = payload[key]
    if not isinstance(value, list | tuple):
        raise UnityTraceIngestError(f"{key} must be an array")
    result = tuple(float(item) for item in value)
    if length is not None and len(result) != length:
        raise UnityTraceIngestError(f"{key} must contain {length} numbers")
    return result


def _new_run_id() -> str:
    return f"unity-{datetime.now(tz=UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"

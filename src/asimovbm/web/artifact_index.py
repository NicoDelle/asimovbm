"""Read local validation artifacts for dashboard APIs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ArtifactLoadError:
    path: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "reason": self.reason}


@dataclass(frozen=True)
class RunSummary:
    run_id: str
    status: str
    created_at: str | None
    viewer_mode: str | None
    trace_backend: str | None
    real_backend_verified: bool
    selected_episode_ids: tuple[str, ...]
    reliability: dict[str, Any]
    errors: tuple[ArtifactLoadError, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "created_at": self.created_at,
            "viewer_mode": self.viewer_mode,
            "trace_backend": self.trace_backend,
            "real_backend_verified": self.real_backend_verified,
            "selected_episode_ids": list(self.selected_episode_ids),
            "reliability": self.reliability,
            "errors": [error.to_dict() for error in self.errors],
        }


def list_runs(artifact_root: Path | str) -> list[dict[str, Any]]:
    root = Path(artifact_root)
    if not root.exists():
        return []
    summaries = [_summarize_run(path) for path in root.iterdir() if path.is_dir()]
    summaries.sort(key=lambda summary: summary.created_at or summary.run_id, reverse=True)
    return [summary.to_dict() for summary in summaries]


def load_run(artifact_root: Path | str, run_id: str) -> dict[str, Any]:
    root = Path(artifact_root).resolve()
    run_dir = _safe_child(root, run_id)
    if not run_dir.exists() or not run_dir.is_dir():
        raise FileNotFoundError(f"unknown run id: {run_id}")
    manifest, manifest_error = _read_json(run_dir / "manifest.json")
    report, report_error = _read_json(run_dir / "report.json")
    errors = [error for error in (manifest_error, report_error) if error is not None]
    records: list[dict[str, Any]] = []
    if isinstance(manifest, dict):
        for record in manifest.get("records", []):
            records.append(_load_record(run_dir, record, errors))
    status = "ready" if not errors else "incomplete"
    return {
        "run_id": run_id,
        "status": status,
        "manifest": manifest,
        "report": report,
        "records": records,
        "errors": [error.to_dict() for error in errors],
    }


def _summarize_run(run_dir: Path) -> RunSummary:
    manifest, manifest_error = _read_json(run_dir / "manifest.json")
    report, report_error = _read_json(run_dir / "report.json")
    errors = tuple(error for error in (manifest_error, report_error) if error is not None)
    if not isinstance(manifest, dict):
        return RunSummary(
            run_id=run_dir.name,
            status="incomplete",
            created_at=None,
            viewer_mode=None,
            trace_backend=None,
            real_backend_verified=False,
            selected_episode_ids=(),
            reliability={},
            errors=errors,
        )
    reliability = {}
    if isinstance(report, dict):
        reliability = dict(report.get("technical_reliability", {}))
    return RunSummary(
        run_id=str(manifest.get("run_id", run_dir.name)),
        status="ready" if not errors else "incomplete",
        created_at=manifest.get("created_at"),
        viewer_mode=manifest.get("viewer_mode"),
        trace_backend=manifest.get("trace_backend"),
        real_backend_verified=_manifest_real_backend_verified(manifest),
        selected_episode_ids=tuple(str(value) for value in manifest.get("selected_episode_ids", ())),
        reliability=reliability,
        errors=errors,
    )


def _load_record(
    run_dir: Path,
    record: Any,
    errors: list[ArtifactLoadError],
) -> dict[str, Any]:
    if not isinstance(record, dict):
        return {"status": "invalid_record", "record": record}
    payload = dict(record)
    metrics_path = record.get("metrics_path")
    trace_path = record.get("trace_path")
    if isinstance(metrics_path, str):
        metrics, error = _read_json(_safe_child(run_dir, metrics_path))
        if error is not None:
            errors.append(error)
        payload["metrics"] = metrics
    if isinstance(trace_path, str):
        payload["trace_exists"] = _safe_child(run_dir, trace_path).exists()
    return payload


def _manifest_real_backend_verified(manifest: dict[str, Any]) -> bool:
    records = manifest.get("records")
    if not isinstance(records, list) or not records:
        return False
    return all(bool(record.get("real_backend_verified", False)) for record in records if isinstance(record, dict))


def _read_json(path: Path) -> tuple[Any | None, ArtifactLoadError | None]:
    if not path.exists():
        return None, ArtifactLoadError(path.as_posix(), "missing")
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except json.JSONDecodeError as exc:
        return None, ArtifactLoadError(path.as_posix(), f"invalid_json: {exc.msg}")


def _safe_child(root: Path, child: str | Path) -> Path:
    root_resolved = root.resolve()
    candidate = Path(child)
    if not candidate.is_absolute():
        candidate = root_resolved / candidate
    candidate_resolved = candidate.resolve(strict=False)
    if candidate_resolved != root_resolved and root_resolved not in candidate_resolved.parents:
        raise ValueError("artifact path escapes configured root")
    return candidate_resolved

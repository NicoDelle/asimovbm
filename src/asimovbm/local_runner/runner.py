"""Sequential local runner for the canonical `g1_slam` episodes."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from asimovbm.reports import JsonReportInput, build_json_report

from .artifacts import prepare_run_dir, relative_to_run, write_json
from .backends import G1SlamReferenceBackend, LocalTraceBackend, backend_proof_for
from .catalog import EpisodeCatalog, load_default_catalog
from .metrics_bridge import build_trace_metric_report
from .traces import LocalRunRecord


@dataclass(frozen=True)
class LocalRunConfig:
    artifact_root: Path = Path("artifacts/local-validation")
    iterations: int = 1
    episode_ids: tuple[str, ...] = ()
    visible: bool | None = None
    viewer_speed: float = 4.0
    run_id: str | None = None
    catalog: EpisodeCatalog | None = None
    backend: LocalTraceBackend | None = None
    extra_metadata: dict[str, Any] = field(default_factory=dict)

    def resolved_visible(self) -> bool:
        if self.visible is not None:
            return self.visible
        return self.iterations == 1

    def validate(self) -> None:
        if self.iterations < 1:
            raise ValueError("iterations must be >= 1")
        if self.viewer_speed <= 0.0:
            raise ValueError("viewer_speed must be > 0")


@dataclass(frozen=True)
class LocalRunResult:
    run_id: str
    run_dir: Path
    manifest_path: Path
    records: tuple[LocalRunRecord, ...]
    report_path: Path


def run_local_validation(config: LocalRunConfig | None = None) -> LocalRunResult:
    config = config or LocalRunConfig()
    config.validate()
    catalog = config.catalog or load_default_catalog()
    backend = config.backend or G1SlamReferenceBackend()
    visible = config.resolved_visible()
    run_id = config.run_id or _new_run_id()
    paths = prepare_run_dir(config.artifact_root, run_id)
    records: list[LocalRunRecord] = []

    for iteration in range(config.iterations):
        for spec in catalog.select(config.episode_ids):
            trace = backend.run_episode(
                spec,
                iteration=iteration,
                viewer_enabled=visible,
                viewer_speed=config.viewer_speed,
            )
            trace = _with_episode_metadata(trace, spec)
            episode_dir = paths.run_dir / spec.id / f"iteration-{iteration:03d}"
            trace_path = episode_dir / "trace.json"
            metrics_path = episode_dir / "metrics.json"
            metric_report = build_trace_metric_report(trace)
            write_json(trace_path, trace.to_dict())
            write_json(metrics_path, metric_report)
            records.append(
                LocalRunRecord(
                    trace=trace,
                    metrics=metric_report,
                    trace_path=relative_to_run(trace_path, paths.run_dir),
                    metrics_path=relative_to_run(metrics_path, paths.run_dir),
                )
            )

    report_path = paths.run_dir / "report.json"
    report = _build_run_report(run_id, records)
    write_json(report_path, report)
    manifest = _build_manifest(config, catalog, records, run_id, relative_to_run(report_path, paths.run_dir))
    write_json(paths.manifest_path, manifest)
    return LocalRunResult(
        run_id=run_id,
        run_dir=paths.run_dir,
        manifest_path=paths.manifest_path,
        records=tuple(records),
        report_path=report_path,
    )


def _with_episode_metadata(trace, spec):
    metadata = dict(trace.metadata)
    metadata.update(
        {
            "start": (spec.config.start.x, spec.config.start.y),
            "goal": spec.config.goal,
            "episode_title": spec.title,
            "config_checksum_sha256": spec.checksum_sha256,
        }
    )
    return trace.__class__(
        episode_id=trace.episode_id,
        iteration=trace.iteration,
        tier_id=trace.tier_id,
        technical_valid=trace.technical_valid,
        terminal_status=trace.terminal_status,
        steps=trace.steps,
        config_checksum_sha256=trace.config_checksum_sha256,
        config_path=trace.config_path,
        robot_selector=trace.robot_selector,
        canonical_backend_id=trace.canonical_backend_id,
        execution_backend_id=trace.execution_backend_id,
        viewer_mode=trace.viewer_mode,
        metadata=metadata,
    )


def _build_run_report(run_id: str, records: list[LocalRunRecord]) -> dict[str, Any]:
    scored = [record.metrics["behavioral_metrics"] for record in records]
    reliability = {
        "total_episode_runs": len(records),
        "technical_valid_episode_runs": sum(1 for record in records if record.trace.technical_valid),
        "technical_failures": sum(1 for record in records if not record.trace.technical_valid),
    }
    return build_json_report(
        JsonReportInput(
            run_id=run_id,
            maturity="local_g1_slam_validation",
            reliability=reliability,
            behavioral_metrics={
                "status": "per_episode",
                "episode_blocks": scored,
            },
        )
    )


def _build_manifest(
    config: LocalRunConfig,
    catalog: EpisodeCatalog,
    records: list[LocalRunRecord],
    run_id: str,
    report_path: str,
) -> dict[str, Any]:
    selected_specs = catalog.select(config.episode_ids)
    return {
        "schema_version": "asimovbm.local_validation.v1",
        "run_id": run_id,
        "created_at": datetime.now(tz=UTC).isoformat(),
        "iterations": config.iterations,
        "viewer_mode": "visible" if config.resolved_visible() else "headless",
        "viewer_speed": config.viewer_speed,
        "canonical_episode_ids": catalog.episode_ids,
        "selected_episode_ids": tuple(spec.id for spec in selected_specs),
        "episodes": [spec.to_manifest() for spec in selected_specs],
        "backend_proof": [backend_proof_for(spec).to_dict() for spec in selected_specs],
        "report_path": report_path,
        "records": [record.to_manifest_entry() for record in records],
        "metadata": dict(config.extra_metadata),
    }


def _new_run_id() -> str:
    return f"local-{datetime.now(tz=UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"

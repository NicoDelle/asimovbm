"""Sequential local runner for the canonical `g1_slam` episodes."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from math import isfinite
from pathlib import Path
from typing import Any
from uuid import uuid4

from asimovbm.reports import JsonReportInput, build_json_report

from .artifacts import prepare_run_dir, relative_to_run, write_json
from .backends import G1SlamReferenceBackend, LocalTraceBackend, backend_proof_for
from .catalog import EpisodeCatalog, load_default_catalog
from .metrics_bridge import build_trace_metric_report
from .public_observation import public_observation_violations
from .traces import MEASUREMENT_PROOF_LEVELS, LocalEpisodeTrace, LocalRunRecord


@dataclass(frozen=True)
class LocalRunConfig:
    artifact_root: Path = Path("artifacts/local-validation")
    iterations: int = 1
    episode_ids: tuple[str, ...] = ()
    visible: bool | None = None
    run_id: str | None = None
    catalog: EpisodeCatalog | None = None
    backend: LocalTraceBackend | None = None
    measurement_backend: str = "reference"
    extra_metadata: dict[str, Any] = field(default_factory=dict)

    def resolved_visible(self) -> bool:
        if self.visible is not None:
            return self.visible
        return self.iterations == 1

    def validate(self) -> None:
        if self.iterations < 1:
            raise ValueError("iterations must be >= 1")
        if self.measurement_backend not in {"reference", "mujoco"}:
            raise ValueError("measurement_backend must be 'reference' or 'mujoco'")


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
    backend = config.backend or _backend_for_measurement(config.measurement_backend)
    visible = config.resolved_visible()
    run_id = config.run_id or _new_run_id()
    paths = prepare_run_dir(config.artifact_root, run_id)
    records: list[LocalRunRecord] = []

    for iteration in range(config.iterations):
        for spec in catalog.select(config.episode_ids):
            trace = backend.run_episode(spec, iteration=iteration, viewer_enabled=visible)
            trace = _with_episode_metadata(trace, spec)
            trace = _with_validation_summary(trace)
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
        measurement_backend_id=trace.measurement_backend_id,
        measurement_proof_level=trace.measurement_proof_level,
        validation_summary=trace.validation_summary,
        metadata=metadata,
    )


def _with_validation_summary(trace: LocalEpisodeTrace) -> LocalEpisodeTrace:
    validation = _validate_trace(trace)
    technical_valid = trace.technical_valid and validation["status"] == "valid"
    terminal_status = trace.terminal_status
    if trace.technical_valid and validation["status"] != "valid":
        terminal_status = "technical_validation_failed"
    metadata = dict(trace.metadata)
    metadata["validation"] = validation
    return LocalEpisodeTrace(
        episode_id=trace.episode_id,
        iteration=trace.iteration,
        tier_id=trace.tier_id,
        technical_valid=technical_valid,
        terminal_status=terminal_status,
        steps=trace.steps,
        config_checksum_sha256=trace.config_checksum_sha256,
        config_path=trace.config_path,
        robot_selector=trace.robot_selector,
        canonical_backend_id=trace.canonical_backend_id,
        execution_backend_id=trace.execution_backend_id,
        viewer_mode=trace.viewer_mode,
        measurement_backend_id=trace.measurement_backend_id,
        measurement_proof_level=trace.measurement_proof_level,
        validation_summary=validation,
        metadata=metadata,
    )


def _validate_trace(trace: LocalEpisodeTrace) -> dict[str, Any]:
    issues: list[str] = []
    if trace.measurement_proof_level not in MEASUREMENT_PROOF_LEVELS:
        issues.append(f"invalid measurement_proof_level: {trace.measurement_proof_level}")
    if trace.measurement_proof_level == "asset_mujoco" and not trace.metadata.get("measurement", {}).get("runtime_verified"):
        issues.append("asset_mujoco proof requires runtime_verified measurement metadata")
    previous_time: float | None = None
    for step in trace.steps:
        if step.dt_s <= 0.0 or not isfinite(step.dt_s):
            issues.append(f"step {step.step_id} has invalid dt_s")
        if previous_time is not None and step.time_s <= previous_time:
            issues.append(f"step {step.step_id} time_s is not strictly increasing")
        previous_time = step.time_s
        if not _finite_sequence(step.robot_pose) or not _finite_sequence(step.robot_velocity):
            issues.append(f"step {step.step_id} has non-finite robot state")
        public_violations = public_observation_violations(step.public_observation)
        if public_violations:
            issues.append(f"step {step.step_id} public_observation leaks {', '.join(public_violations)}")
    return {
        "status": "valid" if not issues else "invalid",
        "issue_count": len(issues),
        "issues": tuple(issues),
        "measurement_proof_level": trace.measurement_proof_level,
    }


def _finite_sequence(values: tuple[float, ...]) -> bool:
    return all(isfinite(float(value)) for value in values)


def _backend_for_measurement(measurement_backend: str) -> LocalTraceBackend:
    if measurement_backend == "reference":
        return G1SlamReferenceBackend()
    return UnavailableMuJoCoTraceBackend()


class UnavailableMuJoCoTraceBackend:
    backend_id = "mujoco_trace_unavailable"

    def run_episode(self, spec, *, iteration: int, viewer_enabled: bool) -> LocalEpisodeTrace:
        reason = "MuJoCo measurement backend is not implemented in the P0 local runner"
        return LocalEpisodeTrace(
            episode_id=spec.id,
            iteration=iteration,
            tier_id="g1_slam_canonical",
            technical_valid=False,
            terminal_status=reason,
            steps=(),
            config_checksum_sha256=spec.checksum_sha256,
            config_path=spec.path.as_posix(),
            robot_selector=spec.robot_selector,
            canonical_backend_id=spec.canonical_backend_id,
            execution_backend_id=self.backend_id,
            viewer_mode="visible" if viewer_enabled else "headless",
            measurement_backend_id="mujoco",
            measurement_proof_level="unavailable",
            metadata={
                "measurement": {
                    "backend_id": "mujoco",
                    "proof_level": "unavailable",
                    "proof_status": "unavailable",
                    "reason": reason,
                }
            },
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
        "measurement_backend": config.measurement_backend,
        "canonical_episode_ids": catalog.episode_ids,
        "selected_episode_ids": tuple(spec.id for spec in selected_specs),
        "episodes": [spec.to_manifest() for spec in selected_specs],
        "backend_proof": [backend_proof_for(spec).to_dict() for spec in selected_specs],
        "measurement_proof": _measurement_proof(records),
        "report_path": report_path,
        "records": [record.to_manifest_entry() for record in records],
        "metadata": dict(config.extra_metadata),
    }


def _measurement_proof(records: list[LocalRunRecord]) -> dict[str, Any]:
    levels = sorted({record.trace.measurement_proof_level for record in records})
    return {
        "levels": levels,
        "episode_runs": [
            {
                "episode_id": record.trace.episode_id,
                "iteration": record.trace.iteration,
                "measurement_backend_id": record.trace.measurement_backend_id,
                "measurement_proof_level": record.trace.measurement_proof_level,
                "validation_status": record.trace.validation_summary.get("status"),
            }
            for record in records
        ],
    }


def _new_run_id() -> str:
    return f"local-{datetime.now(tz=UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"

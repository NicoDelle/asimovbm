"""Sequential local runner for the canonical `g1_slam` episodes."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from math import fsum
from pathlib import Path
from typing import Any
from uuid import uuid4

from asimovbm.metrics import SOCIAL_NAVIGATION_AXIS_IDS
from asimovbm.metrics.scoring import global_score_from_axes, snap_score
from asimovbm.metrics.weights import (
    WEIGHT_MODEL_KIND,
    WEIGHT_MODEL_SOURCE,
    WEIGHT_MODEL_VERSION,
)
from asimovbm.reports import (
    JsonReportInput,
    append_episode_metrics_csv_row,
    build_episode_metrics_csv_row,
    build_json_report,
)

from .artifacts import (
    allocate_episode_metrics_csv_path,
    prepare_run_dir,
    relative_to_run,
    write_json,
)
from .backends import G1SlamReferenceBackend, LocalTraceBackend, backend_proof_for
from .catalog import (
    DEFAULT_POLICY_BY_ROBOT,
    ROBOT_IDS,
    EpisodeCatalog,
    load_default_catalog,
)
from .metrics_bridge import build_trace_metric_report
from .traces import LocalRunRecord


@dataclass(frozen=True)
class LocalRunConfig:
    artifact_root: Path = Path("artifacts/local-validation")
    iterations: int = 1
    robot_id: str | None = None
    policy_id: str | None = None
    policy_path: Path | None = None
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
        if self.robot_id not in ROBOT_IDS:
            raise ValueError(f"robot_id must be one of {', '.join(ROBOT_IDS)}")

    def effective_policy_id(self) -> str:
        if self.robot_id is None:
            raise ValueError("robot_id is required")
        return self.policy_id or DEFAULT_POLICY_BY_ROBOT[self.robot_id]


@dataclass(frozen=True)
class LocalRunResult:
    run_id: str
    run_dir: Path
    manifest_path: Path
    records: tuple[LocalRunRecord, ...]
    report_path: Path
    metrics_csv_path: Path


def run_local_validation(config: LocalRunConfig | None = None) -> LocalRunResult:
    config = config or LocalRunConfig()
    config.validate()
    catalog = config.catalog or load_default_catalog()
    backend = config.backend or G1SlamReferenceBackend()
    visible = config.resolved_visible()
    run_id = config.run_id or _new_run_id()
    paths = prepare_run_dir(config.artifact_root, run_id)
    metrics_csv_path = allocate_episode_metrics_csv_path(config.artifact_root, paths.run_dir)
    records: list[LocalRunRecord] = []

    for iteration in range(config.iterations):
        for spec in _selected_specs(config, catalog):
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
            append_episode_metrics_csv_row(
                metrics_csv_path,
                build_episode_metrics_csv_row(
                    run_id,
                    metric_report,
                    episode_title=spec.title,
                    tier_id=trace.tier_id,
                ),
            )
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
    manifest = _build_manifest(
        config,
        catalog,
        records,
        run_id,
        relative_to_run(report_path, paths.run_dir),
        relative_to_run(metrics_csv_path, paths.run_dir),
    )
    write_json(paths.manifest_path, manifest)
    return LocalRunResult(
        run_id=run_id,
        run_dir=paths.run_dir,
        manifest_path=paths.manifest_path,
        records=tuple(records),
        report_path=report_path,
        metrics_csv_path=metrics_csv_path,
    )


def _with_episode_metadata(trace, spec):
    metadata = dict(trace.metadata)
    metadata.update(
        {
            "start": (spec.config.start.x, spec.config.start.y),
            "goal": spec.config.goal,
            "episode_title": spec.title,
            "config_checksum_sha256": spec.checksum_sha256,
            "robot_id": spec.robot_id,
            "policy_id": spec.policy_id,
            "policy_path": spec.config.locomotion.policy_path.as_posix()
            if spec.config.locomotion.policy_path is not None
            else None,
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
            behavioral_metrics=_build_suite_behavioral_metrics(records),
        )
    )


def _build_suite_behavioral_metrics(records: list[LocalRunRecord]) -> dict[str, Any]:
    episode_blocks = [_episode_behavioral_block(record) for record in records]
    axes = {
        axis_id: _aggregate_suite_axis(axis_id, episode_blocks)
        for axis_id in SOCIAL_NAVIGATION_AXIS_IDS
    }
    status = _suite_behavioral_status(axes)
    global_score = global_score_from_axes(
        axes,
        cap_key="source_episode_caps",
        axis_model="equal_weight_episode_axis_mean",
        extra_model_metadata={"episode_axis_model": WEIGHT_MODEL_KIND},
    )
    if global_score["status"] == "insufficient_evidence":
        status = "insufficient_evidence"
    return {
        "status": status,
        "aggregation_scope": "suite",
        "scoring_model": _suite_scoring_model(),
        "global_score": global_score,
        "axes": axes,
        "features": {},
        "macro_indicators": list(axes.values()),
        "sub_indicators": [],
        "episode_blocks": episode_blocks,
    }


def _episode_behavioral_block(record: LocalRunRecord) -> dict[str, Any]:
    block = dict(record.metrics["behavioral_metrics"])
    block["episode_id"] = record.metrics.get("episode_id", record.trace.episode_id)
    block["iteration"] = record.metrics.get("iteration", record.trace.iteration)
    return block


def _aggregate_suite_axis(axis_id: str, episode_blocks: list[dict[str, Any]]) -> dict[str, Any]:
    scores: list[float] = []
    contributing: list[dict[str, Any]] = []
    omitted: list[dict[str, Any]] = []
    source_caps: list[dict[str, Any]] = []
    source_evidence_gaps: list[dict[str, Any]] = []
    for block in episode_blocks:
        axis = block.get("axes", {}).get(axis_id, {})
        score = axis.get("score")
        run_ref = {
            "episode_id": block.get("episode_id"),
            "iteration": block.get("iteration"),
        }
        if axis.get("status") == "computed" and isinstance(score, int | float):
            scores.append(float(score))
            contributing.append(run_ref)
            for cap in axis.get("applied_caps", ()):
                source_caps.append({**run_ref, **dict(cap)})
            gaps = _axis_evidence_gaps(axis)
            if gaps:
                source_evidence_gaps.append({**run_ref, "evidence_gaps": gaps})
        else:
            omitted.append(
                {
                    **run_ref,
                    "status": axis.get("status", "missing"),
                    "reason": axis.get("reason"),
                }
            )
    if not scores:
        status = _unscored_suite_axis_status(omitted)
        return {
            "axis_id": axis_id,
            "status": status,
            "score": None,
            "confidence": status,
            "contributing_episode_runs": (),
            "omitted_episode_runs": tuple(omitted),
            "model_metadata": _suite_scoring_model(),
            "reason": _unscored_suite_axis_reason(status),
        }
    score = snap_score(fsum(scores) / len(scores))
    return {
        "axis_id": axis_id,
        "status": "computed",
        "score": score,
        "confidence": "sufficient" if not omitted and not source_evidence_gaps else "partial",
        "contributing_episode_runs": tuple(contributing),
        "omitted_episode_runs": tuple(omitted),
        "model_metadata": _suite_scoring_model(),
        "source_episode_caps": tuple(source_caps),
        "source_episode_evidence_gaps": tuple(source_evidence_gaps),
    }


def _suite_scoring_model() -> dict[str, str]:
    return {
        "kind": "equal_weight_episode_axis_mean",
        "version": WEIGHT_MODEL_VERSION,
        "source": WEIGHT_MODEL_SOURCE,
        "episode_axis_model": WEIGHT_MODEL_KIND,
    }


def _axis_evidence_gaps(axis: dict[str, Any]) -> tuple[str, ...]:
    omitted = axis.get("omitted_feature_statuses", {})
    if not isinstance(omitted, dict):
        return ()
    return tuple(
        feature_id
        for feature_id, status in omitted.items()
        if status in {"insufficient_evidence", "invalid_input", "missing"}
    )


def _suite_behavioral_status(axes: dict[str, dict[str, Any]]) -> str:
    statuses = {axis["status"] for axis in axes.values()}
    if "computed" in statuses:
        return "scored"
    if statuses and statuses <= {"not_applicable"}:
        return "not_applicable"
    if "invalid_input" in statuses:
        return "invalid_input"
    return "insufficient_evidence"


def _unscored_suite_axis_status(omitted: list[dict[str, Any]]) -> str:
    statuses = {str(run.get("status")) for run in omitted}
    if statuses and statuses <= {"not_applicable"}:
        return "not_applicable"
    if "invalid_input" in statuses:
        return "invalid_input"
    return "insufficient_evidence"


def _unscored_suite_axis_reason(status: str) -> str:
    if status == "not_applicable":
        return "no episode-level axis scores were applicable"
    if status == "invalid_input":
        return "no episode-level axis scores were computed and at least one had invalid input"
    return "no episode-level axis scores had enough evidence to score"


def _build_manifest(
    config: LocalRunConfig,
    catalog: EpisodeCatalog,
    records: list[LocalRunRecord],
    run_id: str,
    report_path: str,
    metrics_csv_path: str,
) -> dict[str, Any]:
    selected_specs = _selected_specs(config, catalog)
    return {
        "schema_version": "asimovbm.local_validation.v1",
        "run_id": run_id,
        "created_at": datetime.now(tz=UTC).isoformat(),
        "iterations": config.iterations,
        "robot_id": config.robot_id,
        "policy_id": config.effective_policy_id(),
        "policy_path": config.policy_path.as_posix() if config.policy_path is not None else None,
        "viewer_mode": "visible" if config.resolved_visible() else "headless",
        "viewer_speed": config.viewer_speed,
        "canonical_episode_ids": catalog.episode_ids,
        "selected_episode_ids": tuple(spec.id for spec in selected_specs),
        "episodes": [spec.to_manifest() for spec in selected_specs],
        "backend_proof": [backend_proof_for(spec).to_dict() for spec in selected_specs],
        "report_path": report_path,
        "metrics_csv_path": metrics_csv_path,
        "records": [record.to_manifest_entry() for record in records],
        "metadata": dict(config.extra_metadata),
    }


def _new_run_id() -> str:
    return f"local-{datetime.now(tz=UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"


def _selected_specs(config: LocalRunConfig, catalog: EpisodeCatalog):
    return catalog.select(
        config.episode_ids,
        robot_id=config.robot_id,
        policy_id=config.effective_policy_id(),
        policy_path=config.policy_path,
    )

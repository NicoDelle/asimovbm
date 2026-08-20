"""Sequential local runner for the canonical `g1_slam` episodes."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
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
from .backends import G1SlamReferenceBackend, LocalTraceBackend
from .catalog import (
    DEFAULT_POLICY_BY_ROBOT,
    ROBOT_IDS,
    EpisodeCatalog,
    load_default_catalog,
)
from .metrics_bridge import build_trace_metric_report
from .real_backends import G1RoboJuDoRealTraceBackend
from .survey_export import (
    DEFAULT_SURVEY_VIEWS,
    SurveyExportResult,
    SurveyVideoExportConfig,
    export_survey_videos,
)
from .traces import LocalRunRecord


G1_SURVEY_POLICY_ID_BY_PROFILE: dict[str, str] = {
    "g1_robojudo_unitree": "policy_a",
    "g1_robojudo_asap": "policy_b",
}

SURVEY_TIMING_START_DELAY_OVERRIDES: dict[tuple[str, str], float] = {
    ("g1_point_to_point_dynamic_npcs", "g1_robojudo_asap"): 0.0,
}

SURVEY_START_X_OFFSETS_M: dict[tuple[str, str], float] = {
    ("g1_point_to_point_dynamic_npcs", "g1_robojudo_asap"): 0.35,
}


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
    camera_view: str = "config"
    episode_steps: int | None = None
    start_delay_s: float | None = None
    start_x_offset_m: float | None = None
    route_y_offset_m: float | None = None
    trace_backend: str = "reference"
    survey_export: bool = False
    survey_root: Path = Path("artifacts/survey")
    survey_policy_id: str | None = None
    survey_views: tuple[str, ...] = DEFAULT_SURVEY_VIEWS
    survey_video_fps: int = 24
    survey_video_width: int = 1280
    survey_video_height: int = 720
    survey_video_max_duration_s: float | None = 15.0
    run_id: str | None = None
    catalog: EpisodeCatalog | None = None
    backend: LocalTraceBackend | None = None
    extra_metadata: dict[str, Any] = field(default_factory=dict)

    def resolved_visible(self) -> bool:
        if self.visible is not None:
            return self.visible
        if self.survey_export:
            return False
        return self.iterations == 1

    def validate(self) -> None:
        if self.iterations < 1:
            raise ValueError("iterations must be >= 1")
        if self.viewer_speed <= 0.0:
            raise ValueError("viewer_speed must be > 0")
        if self.camera_view not in {"config", "arrival", "bystander"}:
            raise ValueError("camera_view must be one of config, arrival, bystander")
        if self.episode_steps is not None and self.episode_steps < 1:
            raise ValueError("episode_steps must be >= 1")
        if self.start_delay_s is not None and self.start_delay_s < 0.0:
            raise ValueError("start_delay must be >= 0")
        if self.trace_backend not in {"reference", "real"}:
            raise ValueError("trace_backend must be one of reference, real")
        if self.robot_id not in ROBOT_IDS:
            raise ValueError(f"robot_id must be one of {', '.join(ROBOT_IDS)}")
        if self.trace_backend == "real" and self.robot_id != "g1" and self.backend is None:
            raise ValueError("real trace backend currently supports only --robot g1")
        if self.survey_export:
            expected_survey_policy_id = G1_SURVEY_POLICY_ID_BY_PROFILE.get(self.effective_policy_id())
            if (
                self.robot_id == "g1"
                and self.survey_policy_id in {"policy_a", "policy_b"}
                and expected_survey_policy_id is not None
                and self.survey_policy_id != expected_survey_policy_id
            ):
                raise ValueError(
                    f"{self.effective_policy_id()} maps to survey {expected_survey_policy_id}; "
                    f"got --survey-policy-id {self.survey_policy_id}"
                )
            SurveyVideoExportConfig(
                survey_root=self.survey_root,
                policy_id=self.survey_policy_id,
                views=self.survey_views,
                fps=self.survey_video_fps,
                width=self.survey_video_width,
                height=self.survey_video_height,
                max_duration_s=self.survey_video_max_duration_s,
            ).validate()

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
    survey_export: SurveyExportResult | None = None


def run_local_validation(config: LocalRunConfig | None = None) -> LocalRunResult:
    config = config or LocalRunConfig()
    config.validate()
    catalog = config.catalog or load_default_catalog()
    backend = config.backend or _backend_for_config(config)
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
                camera_view=config.camera_view,
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
                    canonical_backend_id=trace.canonical_backend_id,
                    execution_backend_id=trace.execution_backend_id,
                    trace_source=str(trace.metadata.get("trace_source", "")),
                    real_backend_verified=bool(trace.metadata.get("real_backend_verified", False)),
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
    selected_specs = _selected_specs(config, catalog)
    survey_export = None
    if config.survey_export:
        survey_export = export_survey_videos(
            run_id=run_id,
            specs_by_id={spec.id: spec for spec in selected_specs},
            records=records,
            config=SurveyVideoExportConfig(
                survey_root=config.survey_root,
                policy_id=config.survey_policy_id,
                views=config.survey_views,
                fps=config.survey_video_fps,
                width=config.survey_video_width,
                height=config.survey_video_height,
                max_duration_s=config.survey_video_max_duration_s,
            ),
        )
    manifest = _build_manifest(
        config,
        selected_specs,
        records,
        run_id,
        relative_to_run(report_path, paths.run_dir),
        relative_to_run(metrics_csv_path, paths.run_dir),
        survey_export,
    )
    write_json(paths.manifest_path, manifest)
    return LocalRunResult(
        run_id=run_id,
        run_dir=paths.run_dir,
        manifest_path=paths.manifest_path,
        records=tuple(records),
        report_path=report_path,
        metrics_csv_path=metrics_csv_path,
        survey_export=survey_export,
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
            "controller_start_delay_s": spec.config.controller.start_delay_s,
            "start_x_offset_m": spec.raw_config.get("local_start_x_offset_m", 0.0),
            "route_y_offset_m": spec.raw_config.get("local_route_y_offset_m", 0.0),
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
    selected_specs,
    records: list[LocalRunRecord],
    run_id: str,
    report_path: str,
    metrics_csv_path: str,
    survey_export: SurveyExportResult | None,
) -> dict[str, Any]:
    manifest = {
        "schema_version": "asimovbm.local_validation.v1",
        "run_id": run_id,
        "created_at": datetime.now(tz=UTC).isoformat(),
        "iterations": config.iterations,
        "robot_id": config.robot_id,
        "policy_id": config.effective_policy_id(),
        "policy_path": config.policy_path.as_posix() if config.policy_path is not None else None,
        "viewer_mode": "visible" if config.resolved_visible() else "headless",
        "viewer_speed": config.viewer_speed,
        "camera_view": config.camera_view,
        "trace_backend": config.trace_backend,
        "start_delay_s": config.start_delay_s,
        "start_x_offset_m": config.start_x_offset_m,
        "route_y_offset_m": config.route_y_offset_m,
        "canonical_episode_ids": tuple(spec.id for spec in selected_specs),
        "selected_episode_ids": tuple(spec.id for spec in selected_specs),
        "episodes": [spec.to_manifest() for spec in selected_specs],
        "backend_proof": [_backend_proof_from_record(record) for record in records],
        "report_path": report_path,
        "metrics_csv_path": metrics_csv_path,
        "records": [record.to_manifest_entry() for record in records],
        "metadata": dict(config.extra_metadata),
    }
    if survey_export is not None:
        manifest["survey_export"] = survey_export.to_manifest_entry()
    return manifest


def _backend_for_config(config: LocalRunConfig) -> LocalTraceBackend:
    if config.trace_backend == "real":
        return G1RoboJuDoRealTraceBackend()
    return G1SlamReferenceBackend()


def _backend_proof_from_record(record: LocalRunRecord) -> dict[str, Any]:
    trace = record.trace
    real_backend_verified = bool(trace.metadata.get("real_backend_verified", False))
    return {
        "episode_id": trace.episode_id,
        "iteration": trace.iteration,
        "canonical_backend_id": trace.canonical_backend_id,
        "robot_selector": trace.robot_selector,
        "execution_backend_id": trace.execution_backend_id,
        "trace_source": trace.metadata.get("trace_source"),
        "real_backend_verified": real_backend_verified,
        "proof_status": trace.metadata.get(
            "backend_proof_status",
            "verified_in_this_run" if real_backend_verified else "not_verified_in_this_run",
        ),
        "reason": trace.metadata.get(
            "backend_proof_reason",
            None if real_backend_verified else "metrics came from reference trace backend",
        ),
    }


def _new_run_id() -> str:
    return f"local-{datetime.now(tz=UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"


def _selected_specs(config: LocalRunConfig, catalog: EpisodeCatalog):
    specs = catalog.select(
        config.episode_ids,
        robot_id=config.robot_id,
        policy_id=config.effective_policy_id(),
        policy_path=config.policy_path,
    )
    adjusted_specs = []
    for spec in specs:
        spec_config = spec.config
        if config.episode_steps is not None:
            spec_config = replace(spec_config, steps=config.episode_steps)
        start_delay_s = _effective_start_delay_s(config, spec)
        if start_delay_s is not None:
            spec_config = replace(
                spec_config,
                controller=replace(spec_config.controller, start_delay_s=start_delay_s),
            )
        start_x_offset_m = _start_x_offset_m(config, spec)
        route_y_offset_m = _route_y_offset_m(config, spec)
        if start_x_offset_m or route_y_offset_m:
            spec_config = replace(
                spec_config,
                start=replace(
                    spec_config.start,
                    x=spec_config.start.x + start_x_offset_m,
                    y=spec_config.start.y + route_y_offset_m,
                ),
                goal=(spec_config.goal[0], spec_config.goal[1] + route_y_offset_m),
            )
        adjusted_specs.append(
            replace(
                spec,
                config=spec_config,
                raw_config={
                    **spec.raw_config,
                    "local_start_x_offset_m": start_x_offset_m,
                    "local_route_y_offset_m": route_y_offset_m,
                },
            )
        )
    return tuple(adjusted_specs)


def _effective_start_delay_s(config: LocalRunConfig, spec) -> float | None:
    if config.start_delay_s is not None:
        return config.start_delay_s
    return SURVEY_TIMING_START_DELAY_OVERRIDES.get((spec.id, spec.policy_id))


def _start_x_offset_m(config: LocalRunConfig, spec) -> float:
    if config.start_x_offset_m is not None:
        return config.start_x_offset_m
    return SURVEY_START_X_OFFSETS_M.get((spec.id, spec.policy_id), 0.0)


def _route_y_offset_m(config: LocalRunConfig, spec) -> float:
    if config.route_y_offset_m is not None:
        return config.route_y_offset_m
    return 0.0

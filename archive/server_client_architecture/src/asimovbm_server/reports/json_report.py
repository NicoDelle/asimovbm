"""JSON report scaffolding for smoke and future metric outputs."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any

from asimovbm_server.metrics import (
    SOCIAL_NAVIGATION_AXIS_IDS,
    SOCIAL_NAVIGATION_METRIC_IDS,
    AxisScore,
    MetricStatus,
    MetricValue,
)
from asimovbm_server.simulation import SimulationSmokeResult


class MetricFreezeRequiredError(RuntimeError):
    """Raised when calibrated score mode is requested without metric freeze."""


@dataclass(frozen=True)
class JsonReportConfig:
    metric_freeze_approved: bool = False
    calibrated_scores: bool = False
    metric_spec_ref: str = "docs/specs/social-navigation-metrics.md"


@dataclass(frozen=True)
class JsonReportInput:
    run_id: str
    maturity: str
    reliability: dict[str, Any] = field(default_factory=dict)
    smoke_results: tuple[SimulationSmokeResult, ...] = ()
    behavioral_metrics: dict[str, Any] | None = None


def build_json_report(
    report_input: JsonReportInput,
    config: JsonReportConfig | None = None,
) -> dict[str, Any]:
    config = config or JsonReportConfig()
    if config.calibrated_scores and not config.metric_freeze_approved:
        raise MetricFreezeRequiredError(
            "calibrated score mode requires approved metric freeze"
        )

    return {
        "schema_version": "asimovbm.report.v0",
        "run_id": report_input.run_id,
        "maturity": report_input.maturity,
        "metric_freeze": {
            "approved": config.metric_freeze_approved,
            "spec_ref": config.metric_spec_ref,
        },
        "behavioral_metrics": report_input.behavioral_metrics
        if report_input.behavioral_metrics is not None
        else _behavioral_metric_block(config),
        "technical_reliability": dict(report_input.reliability),
        "smoke_results": [
            smoke.to_report_context() for smoke in report_input.smoke_results
        ],
    }


def _behavioral_metric_block(config: JsonReportConfig) -> dict[str, Any]:
    if config.calibrated_scores:
        return {
            "status": "ready_for_metric_engines",
            "macro_indicators": [],
        }
    return {
        "status": "not_applicable_smoke_context",
        "reason": "behavioral metric engines are gated by metric freeze and social-navigation telemetry",
        "macro_indicators": [],
    }


def build_behavioral_metric_block(
    axis_scores: Mapping[str, AxisScore],
    metric_values: Mapping[str, MetricValue],
) -> dict[str, Any]:
    axes = {
        axis_id: _axis_score_to_report(axis_id, axis_scores)
        for axis_id in SOCIAL_NAVIGATION_AXIS_IDS
    }
    features = {
        metric_id: _metric_value_to_report(
            metric_values.get(metric_id)
            or MetricValue(
                metric_id=metric_id,
                status=MetricStatus.INSUFFICIENT_EVIDENCE,
                reason="metric value was not supplied",
            )
        )
        for metric_id in SOCIAL_NAVIGATION_METRIC_IDS
    }
    return {
        "status": _behavioral_status(axis_scores, metric_values),
        "scoring_model": _scoring_model(axes),
        "axes": axes,
        "features": features,
        "macro_indicators": list(axes.values()),
        "sub_indicators": list(features.values()),
    }


def _axis_score_to_report(
    axis_id: str,
    axis_scores: Mapping[str, AxisScore],
) -> dict[str, Any]:
    axis = axis_scores.get(axis_id)
    if axis is not None:
        return axis.to_report()
    return {
        "axis_id": axis_id,
        "status": MetricStatus.INSUFFICIENT_EVIDENCE.value,
        "score": None,
        "confidence": "insufficient",
        "contributing_features": (),
        "omitted_features": (),
        "omitted_feature_statuses": {},
        "model_metadata": _default_scoring_model(),
        "reason": "axis score was not supplied",
    }


def _metric_value_to_report(value: MetricValue) -> dict[str, Any]:
    payload = asdict(value)
    payload["status"] = value.status.value
    return payload


def _behavioral_status(
    axis_scores: Mapping[str, AxisScore],
    metric_values: Mapping[str, MetricValue],
) -> str:
    if any(axis.status == MetricStatus.COMPUTED for axis in axis_scores.values()):
        return "scored"
    statuses = {value.status for value in metric_values.values()}
    if statuses and statuses <= {MetricStatus.NOT_APPLICABLE}:
        return "not_applicable"
    return "insufficient_evidence" if statuses else "not_applicable"


def _scoring_model(axes: Mapping[str, dict[str, Any]]) -> dict[str, str]:
    for axis in axes.values():
        metadata = axis.get("model_metadata")
        if isinstance(metadata, dict):
            return dict(metadata)
    return _default_scoring_model()


def _default_scoring_model() -> dict[str, str]:
    return {
        "kind": "manual_v0_evidence_weights",
        "version": "v0",
        "source": "docs/specs/social-navigation-metrics.md",
    }

"""JSON report scaffolding for smoke and future metric outputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

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
        "behavioral_metrics": _behavioral_metric_block(config),
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

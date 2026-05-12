from __future__ import annotations

import re
from pathlib import Path

import pytest

from asimovbm_protocol import ActionMessage
from asimovbm_server.reports import (
    JsonReportConfig,
    JsonReportInput,
    MetricFreezeRequiredError,
    build_json_report,
)
from asimovbm_server.simulation import FakeSmokeSimulation

SPEC_PATH = Path("docs/specs/social-navigation-metrics.md")


def _spec_text() -> str:
    return SPEC_PATH.read_text(encoding="utf-8")


def _sections(text: str) -> list[str]:
    text = text.split("## Weight Matrix v0", maxsplit=1)[0]
    parts = re.split(r"^### Sub-indicator: ", text, flags=re.MULTILINE)
    return parts[1:]


def test_metric_spec_names_four_macro_indicators_and_sixteen_subindicators() -> None:
    text = _spec_text()

    macros = re.findall(r"^## Macro: (.+)$", text, flags=re.MULTILINE)
    subindicators = re.findall(
        r"^### Sub-indicator: (.+)$", text, flags=re.MULTILINE
    )

    assert macros == [
        "Perceived Dexterity",
        "Perceived Safety",
        "Perceived Social Awareness",
        "Impression",
    ]
    assert subindicators == [
        "Task Success Rate",
        "Task Completion Time",
        "Comfort-Aware Path Efficiency",
        "Hesitation Rate",
        "Minimum Human–Robot Distance",
        "Proxemic Intrusion Dose",
        "Speed Near Humans (95th percentile)",
        "Gesture Response Success",
        "Acknowledgement Clarity (Target)",
        "Human-Aware Approach (with side/angle term)",
        "Bystander Acknowledgement",
        "Motion Smoothness (SPARC)",
        "Heading Jerk (yaw SPARC)",
        "Stability",
        "Legibility (commit-time)",
        "Behavioral Naturalness (gait/wheel regularity)",
    ]


def test_each_metric_section_has_required_contract_fields() -> None:
    required = [
        "Inputs",
        "Formula",
        "Normalization",
        "Confidence",
        "Sources",
    ]

    for section in _sections(_spec_text()):
        for label in required:
            assert label in section


def test_metric_spec_weight_matrix_uses_registry_feature_ids() -> None:
    from asimovbm_server.metrics import SOCIAL_NAVIGATION_METRIC_IDS

    text = _spec_text()

    for metric_id in SOCIAL_NAVIGATION_METRIC_IDS:
        assert f"| {metric_id}" in text


def test_metric_spec_has_no_placeholder_formulas() -> None:
    text = _spec_text().lower()
    forbidden = ["tbd", "todo", "placeholder", "coming soon"]

    for word in forbidden:
        assert word not in text


def test_report_builder_refuses_calibrated_scores_without_metric_freeze() -> None:
    with pytest.raises(MetricFreezeRequiredError):
        build_json_report(
            JsonReportInput(run_id="run-1", maturity="fake_protocol"),
            JsonReportConfig(calibrated_scores=True, metric_freeze_approved=False),
        )


def test_report_builder_keeps_smoke_metrics_not_applicable() -> None:
    sim = FakeSmokeSimulation()
    step = sim.next_step()

    sim.apply_action(ActionMessage(step.step_id, [0.0], latency_ms=1.0))

    report = build_json_report(
        JsonReportInput(
            run_id="run-1",
            maturity="fake_protocol",
            reliability={"attempts": 1},
            smoke_results=(sim.smoke_result(),),
        )
    )

    assert report["behavioral_metrics"]["status"] == "not_applicable_smoke_context"
    assert report["technical_reliability"]["attempts"] == 1
    assert report["smoke_results"][0]["maturity"] == "fake_protocol"

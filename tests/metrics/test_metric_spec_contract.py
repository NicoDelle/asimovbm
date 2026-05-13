from __future__ import annotations

import re
from pathlib import Path

import pytest

from asimovbm.reports import (
    JsonReportConfig,
    JsonReportInput,
    MetricFreezeRequiredError,
    build_json_report,
)

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
    from asimovbm.metrics import SOCIAL_NAVIGATION_METRIC_IDS

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


def test_report_builder_accepts_local_technical_context() -> None:
    report = build_json_report(
        JsonReportInput(
            run_id="run-1",
            maturity="local_g1_slam_validation",
            reliability={"attempts": 1},
            validation_results=({"maturity": "local_g1_slam_validation", "episode_id": "g1_approach_user"},),
        )
    )

    assert report["behavioral_metrics"]["status"] == "not_applicable"
    assert report["technical_reliability"]["attempts"] == 1
    assert report["validation_results"][0]["maturity"] == "local_g1_slam_validation"

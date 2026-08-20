from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

from asimovbm.metrics import SOCIAL_NAVIGATION_AXIS_IDS, SOCIAL_NAVIGATION_METRIC_IDS
from asimovbm.metrics.weights import V1_EVIDENCE_WEIGHTS, axis_weight_sums, normalized_axis_weights


def test_v1_weight_matrix_matches_metric_and_axis_ids() -> None:
    for axis_id in SOCIAL_NAVIGATION_AXIS_IDS:
        weights = normalized_axis_weights(axis_id)

        assert set(weights).issubset(SOCIAL_NAVIGATION_METRIC_IDS)
        assert math.isclose(sum(weights.values()), 1.0)


def test_v1_weight_matrix_matches_research_artifact_column_sums() -> None:
    assert axis_weight_sums() == {
        "perceived_dexterity": 19.0,
        "perceived_safety": 27.0,
        "perceived_social_awareness": 22.0,
        "impression": 18.5,
    }
    assert V1_EVIDENCE_WEIGHTS["hesitation"]["perceived_safety"] == 1.5
    assert V1_EVIDENCE_WEIGHTS["stability"]["perceived_social_awareness"] == 0
    assert math.isclose(
        normalized_axis_weights("impression")["heading_jerk"],
        1.5 / 18.5,
    )


def test_v1_weight_matrix_matches_full_research_artifact_table() -> None:
    artifact = Path("docs/metrics_research/hri_metric_weighting_artifact.md").read_text(encoding="utf-8")
    table = artifact.split("## Proposed score matrix", 1)[1].split("## Normalized candidate weight matrix", 1)[0]
    expected: dict[str, dict[str, float]] = {}
    for line in table.splitlines():
        match = re.match(
            r"^\| `([^`]+)` \| ([0-9.]+) \| ([0-9.]+) \| ([0-9.]+) \| ([0-9.]+) \|$",
            line.strip(),
        )
        if match is None:
            continue
        metric_id, dexterity, safety, awareness, impression = match.groups()
        expected[metric_id] = {
            "perceived_dexterity": float(dexterity),
            "perceived_safety": float(safety),
            "perceived_social_awareness": float(awareness),
            "impression": float(impression),
        }

    assert expected == V1_EVIDENCE_WEIGHTS


def test_custom_weight_matrix_accepts_valid_noncanonical_mapping_order() -> None:
    reversed_matrix = {
        metric_id: {
            axis_id: V1_EVIDENCE_WEIGHTS[metric_id][axis_id]
            for axis_id in reversed(SOCIAL_NAVIGATION_AXIS_IDS)
        }
        for metric_id in reversed(SOCIAL_NAVIGATION_METRIC_IDS)
    }

    assert math.isclose(sum(normalized_axis_weights("perceived_safety", reversed_matrix).values()), 1.0)


def test_unknown_axis_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown axis"):
        normalized_axis_weights("mystery")

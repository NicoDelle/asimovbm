from __future__ import annotations

import math

import pytest

from asimovbm.metrics import SOCIAL_NAVIGATION_AXIS_IDS, SOCIAL_NAVIGATION_METRIC_IDS
from asimovbm.metrics.weights import normalized_axis_weights


def test_v0_weight_matrix_matches_metric_and_axis_ids() -> None:
    for axis_id in SOCIAL_NAVIGATION_AXIS_IDS:
        weights = normalized_axis_weights(axis_id)

        assert set(weights).issubset(SOCIAL_NAVIGATION_METRIC_IDS)
        assert math.isclose(sum(weights.values()), 1.0)


def test_unknown_axis_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown axis"):
        normalized_axis_weights("mystery")

from __future__ import annotations

import math

from asimovbm.metrics.conventions import (
    angle_error,
    integrate_time_series,
    normalize_higher_is_better,
    normalize_lower_is_better,
    path_length,
    percentile,
)


def test_normalization_clips_at_bounds() -> None:
    assert normalize_higher_is_better(-1.0, good=1.0, bad=0.0) == 0.0
    assert normalize_higher_is_better(2.0, good=1.0, bad=0.0) == 1.0
    assert normalize_lower_is_better(2.0, good=0.0, bad=1.0) == 0.0
    assert normalize_lower_is_better(-1.0, good=0.0, bad=1.0) == 1.0


def test_time_integration_handles_variable_intervals() -> None:
    assert integrate_time_series([0.0, 1.0, 3.0], [0.0, 2.0, 2.0]) == 5.0


def test_path_length_and_angle_helpers_are_hand_checkable() -> None:
    assert path_length([(0.0, 0.0), (3.0, 4.0), (6.0, 8.0)]) == 10.0
    assert math.isclose(angle_error(math.pi - 0.1, -math.pi + 0.1), 0.2)


def test_percentile_interpolates_sorted_values() -> None:
    assert percentile([0.0, 1.0, 2.0, 3.0, 4.0], 95.0) == 3.8

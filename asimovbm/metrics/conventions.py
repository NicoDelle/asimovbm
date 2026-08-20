"""Shared conventions and numeric helpers for social-navigation metrics."""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

EPS = 1e-9


@dataclass(frozen=True)
class MetricConfig:
    d_stop_min: float = 0.8
    d_stop_max: float = 1.4
    t_max: float = 120.0
    d_personal: float = 1.2
    d_hard: float = 0.45
    d_near: float = 2.0
    d_comfort_sat: float = 0.9
    theta_ack_rad: float = math.radians(35.0)
    t_ack: float = 3.0
    v_hes: float = 0.05
    dt_hes: float = 0.5
    sparc_bad: float = -6.0
    sparc_good: float = -2.0
    sparc_yaw_bad: float = -6.0
    sparc_yaw_good: float = -2.0
    commit_cone_rad: float = math.radians(30.0)
    dt_commit: float = 1.0
    d_reversal_min: float = 0.1
    irreg_max: float | None = None


DEFAULT_CONFIG = MetricConfig()


def clip(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return min(upper, max(lower, value))


def normalize_higher_is_better(value: float, *, good: float, bad: float) -> float:
    if math.isclose(good, bad):
        raise ValueError("good and bad thresholds must differ")
    return clip((value - bad) / (good - bad))


def normalize_lower_is_better(value: float, *, good: float, bad: float) -> float:
    if math.isclose(good, bad):
        raise ValueError("good and bad thresholds must differ")
    return clip((bad - value) / (bad - good))


def mean(values: Iterable[float]) -> float | None:
    items = list(values)
    if not items:
        return None
    return sum(items) / len(items)


def distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def path_length(points: Sequence[tuple[float, float]]) -> float:
    if len(points) < 2:
        return 0.0
    return sum(distance(a, b) for a, b in zip(points, points[1:], strict=False))


def integrate_time_series(times: Sequence[float], values: Sequence[float]) -> float:
    if len(times) != len(values):
        raise ValueError("times and values must have the same length")
    if len(times) < 2:
        return 0.0
    total = 0.0
    for start_t, end_t, start_v, end_v in zip(
        times,
        times[1:],
        values,
        values[1:],
        strict=False,
    ):
        dt = end_t - start_t
        if dt < 0:
            raise ValueError("times must be monotonic increasing")
        total += 0.5 * (start_v + end_v) * dt
    return total


def wrap_angle(value: float) -> float:
    return math.atan2(math.sin(value), math.cos(value))


def angle_error(a: float, b: float) -> float:
    return abs(wrap_angle(a - b))


def percentile(values: Sequence[float], pct: float) -> float | None:
    if not values:
        return None
    if pct < 0.0 or pct > 100.0:
        raise ValueError("percentile must be in [0, 100]")
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (pct / 100.0) * (len(ordered) - 1)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[int(rank)]
    frac = rank - lower
    return ordered[lower] * (1.0 - frac) + ordered[upper] * frac


def uniformly_sampled(times: Sequence[float], *, tolerance: float = 1e-6) -> bool:
    if len(times) < 3:
        return True
    intervals = [b - a for a, b in zip(times, times[1:], strict=False)]
    if any(interval <= 0 for interval in intervals):
        return False
    expected = intervals[0]
    return all(abs(interval - expected) <= tolerance for interval in intervals[1:])


def sample_rate_hz(times: Sequence[float]) -> float | None:
    if len(times) < 2:
        return None
    duration = times[-1] - times[0]
    if duration <= 0:
        return None
    return (len(times) - 1) / duration


def contiguous_true_epochs(times: Sequence[float], mask: Sequence[bool]) -> list[tuple[float, float]]:
    if len(times) != len(mask):
        raise ValueError("times and mask must have the same length")
    epochs: list[tuple[float, float]] = []
    start: float | None = None
    for index, active in enumerate(mask):
        if active and start is None:
            start = times[index]
        if not active and start is not None:
            epochs.append((start, times[index]))
            start = None
    if start is not None and times:
        epochs.append((start, times[-1]))
    return epochs

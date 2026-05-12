"""Morphology-aware behavioral naturalness.

This metric replaces a static morphology-task-fit tag with runtime evidence of
natural motion. For legged robots, it measures how well a declared periodic
joint signal fits a sinusoid; for wheeled/mobile-base robots, it measures
lateral velocity relative to forward velocity. Undeclared or unsupported
morphologies return not applicable so the impression axis can rely on the other
motion features instead of penalizing missing calibration.

References:
- Balasubramanian et al. (2012), "A Robust and Sensitive Metric for Quantifying
  Movement Smoothness" (kinematic signal regularity prior; spec source S25).
- Hausdorff (2005), gait variability work using coefficient of variation of
  stride intervals (biomechanics regularity anchor; spec source S27).
- Kruse et al. (2013), "Human-aware robot navigation: A survey" (naturalness as
  motion-level similarity to human/socially acceptable behavior; spec source
  S32).

Benchmark adaptation:
The per-morphology branch and the exact sinusoid/lateral-velocity formulas are
local operationalizations grounded in the cited regularity literature. No
single HRI paper validates this exact score against subjective ratings.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from .conventions import EPS, clip, mean
from .models import MetricStatus, MetricValue


def compute(
    *,
    morphology: str | None,
    irreg_max: float | None,
    joint_signal: Sequence[float] | None = None,
    times: Sequence[float] | None = None,
    lateral_velocities: Sequence[float] | None = None,
    forward_velocities: Sequence[float] | None = None,
) -> MetricValue:
    if morphology is None or irreg_max is None:
        return MetricValue(
            metric_id="behavioral_naturalness",
            status=MetricStatus.NOT_APPLICABLE,
            confidence="not_applicable",
            reason="robot morphology or naturalness calibration is not declared",
        )
    if irreg_max <= 0:
        return MetricValue(
            metric_id="behavioral_naturalness",
            status=MetricStatus.INVALID_INPUT,
            confidence="insufficient",
            reason="irreg_max must be positive",
        )
    if morphology in {"legged", "quadruped", "humanoid"}:
        # Legged naturalness uses a periodic-joint regularity proxy. The robot
        # package should choose the joint signal; this function only scores it.
        if joint_signal is None or times is None or len(joint_signal) != len(times) or len(times) < 4:
            return MetricValue(
                metric_id="behavioral_naturalness",
                status=MetricStatus.INSUFFICIENT_EVIDENCE,
                confidence="low",
                reason="legged naturalness requires periodic joint telemetry",
            )
        irreg = _legged_irregularity(joint_signal, times)
    elif morphology in {"wheeled", "mobile_base"}:
        # Wheeled bases should not look like they are side-slipping. Lateral
        # body-frame motion relative to forward motion is the v1 proxy.
        if (
            lateral_velocities is None
            or forward_velocities is None
            or len(lateral_velocities) != len(forward_velocities)
            or not lateral_velocities
        ):
            return MetricValue(
                metric_id="behavioral_naturalness",
                status=MetricStatus.INSUFFICIENT_EVIDENCE,
                confidence="low",
                reason="wheeled naturalness requires body-frame velocity telemetry",
            )
        irreg = _rms(lateral_velocities) / max(_rms(forward_velocities), EPS)
    else:
        return MetricValue(
            metric_id="behavioral_naturalness",
            status=MetricStatus.NOT_APPLICABLE,
            confidence="not_applicable",
            reason=f"unsupported morphology class: {morphology}",
        )

    score = clip(1.0 - irreg / irreg_max)
    return MetricValue(
        metric_id="behavioral_naturalness",
        status=MetricStatus.COMPUTED,
        raw_value=score,
        normalized_score=score,
        confidence="sufficient",
        units="ratio",
        raw_inputs_summary={"morphology": morphology, "irregularity": irreg},
    )


def _legged_irregularity(signal: Sequence[float], times: Sequence[float]) -> float:
    duration = times[-1] - times[0]
    if duration <= 0:
        return math.inf
    best_error = math.inf
    best_amplitude = 0.0
    max_frequency = min(3.0, max(0.5, len(times) / (2.0 * duration)))
    # Search a small frequency grid rather than requiring scipy/numpy. Explicit
    # common gait frequencies stabilize the result for synthetic and short
    # benchmark traces.
    frequencies = [0.25 + index * (max_frequency - 0.25) / 48.0 for index in range(49)]
    frequencies.extend(
        frequency
        for frequency in (0.5, 1.0, 1.5, 2.0)
        if 0.25 <= frequency <= max_frequency
    )
    for frequency in frequencies:
        omega = 2.0 * math.pi * frequency
        rows = [(math.sin(omega * time), math.cos(omega * time), 1.0) for time in times]
        coeffs = _least_squares_3(rows, signal)
        if coeffs is None:
            continue
        # Fit A*sin(wt) + B*cos(wt) + C; amplitude is sqrt(A^2 + B^2).
        fitted = [a * coeffs[0] + b * coeffs[1] + c * coeffs[2] for a, b, c in rows]
        error = _rms([actual - fit for actual, fit in zip(signal, fitted, strict=True)])
        amplitude = math.hypot(coeffs[0], coeffs[1])
        if error < best_error:
            best_error = error
            best_amplitude = amplitude
    return best_error / max(best_amplitude, EPS)


def _least_squares_3(
    rows: Sequence[tuple[float, float, float]],
    values: Sequence[float],
) -> tuple[float, float, float] | None:
    matrix = [[0.0 for _ in range(3)] for _ in range(3)]
    rhs = [0.0, 0.0, 0.0]
    for row, value in zip(rows, values, strict=True):
        for i in range(3):
            rhs[i] += row[i] * value
            for j in range(3):
                matrix[i][j] += row[i] * row[j]
    return _solve_3x3(matrix, rhs)


def _solve_3x3(matrix: list[list[float]], rhs: list[float]) -> tuple[float, float, float] | None:
    augmented = [row[:] + [rhs_value] for row, rhs_value in zip(matrix, rhs, strict=True)]
    for col in range(3):
        pivot = max(range(col, 3), key=lambda row: abs(augmented[row][col]))
        if abs(augmented[pivot][col]) < EPS:
            return None
        augmented[col], augmented[pivot] = augmented[pivot], augmented[col]
        pivot_value = augmented[col][col]
        for index in range(col, 4):
            augmented[col][index] /= pivot_value
        for row in range(3):
            if row == col:
                continue
            factor = augmented[row][col]
            for index in range(col, 4):
                augmented[row][index] -= factor * augmented[col][index]
    return augmented[0][3], augmented[1][3], augmented[2][3]


def _rms(values: Sequence[float]) -> float:
    value = mean([sample * sample for sample in values])
    return math.sqrt(value or 0.0)

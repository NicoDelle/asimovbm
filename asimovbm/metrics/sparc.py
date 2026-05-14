"""Motion smoothness using spectral arc length.

This module implements SPARC (spectral arc length), a dimensionless smoothness
measure computed from a uniformly sampled kinematic signal. In this benchmark,
`sparc` is used for translational motion smoothness, while `heading_jerk`
reuses the same implementation on yaw-rate samples.

References:
- Balasubramanian et al. (2012), "A Robust and Sensitive Metric for Quantifying
  Movement Smoothness" (original SPARC formula; spec source S25).
- Balasubramanian et al. (2015), "On the Analysis of Movement Smoothness"
  (movement-smoothness interpretation; spec source S18).
- Schulz et al. (2020), "Differences of Human Perceptions of a Robot Moving
  using Linear or Slow in, Slow out Velocity Profiles..." (velocity profile vs
  Godspeed trends in HRI; spec source S17).

Benchmark adaptation:
The implementation uses a tiny standard-library DFT to keep core metrics free
of optional NumPy dependencies. The adaptive cutoff follows the SPARC rule from
Balasubramanian et al.; callers must provide uniformly sampled telemetry.
"""

from __future__ import annotations

import cmath
import math
from collections.abc import Sequence

from .conventions import (
    DEFAULT_CONFIG,
    normalize_higher_is_better,
    sample_rate_hz,
    uniformly_sampled,
)
from .models import MetricStatus, MetricValue


def compute(
    *,
    samples: Sequence[float],
    times: Sequence[float],
    metric_id: str = "sparc",
    bad: float = DEFAULT_CONFIG.sparc_bad,
    good: float = DEFAULT_CONFIG.sparc_good,
) -> MetricValue:
    if len(samples) != len(times):
        return MetricValue(
            metric_id=metric_id,
            status=MetricStatus.INVALID_INPUT,
            confidence="insufficient",
            reason="samples and times must have the same length",
        )
    if len(samples) < 4:
        return MetricValue(
            metric_id=metric_id,
            status=MetricStatus.INSUFFICIENT_EVIDENCE,
            confidence="insufficient",
            reason="SPARC requires at least four samples",
            raw_inputs_summary={"sample_count": len(samples)},
        )
    if not uniformly_sampled(times):
        return MetricValue(
            metric_id=metric_id,
            status=MetricStatus.INSUFFICIENT_EVIDENCE,
            confidence="insufficient",
            reason="SPARC requires uniformly sampled telemetry",
            raw_inputs_summary={"sample_count": len(samples)},
        )
    rate = sample_rate_hz(times)
    if rate is None:
        return MetricValue(
            metric_id=metric_id,
            status=MetricStatus.INSUFFICIENT_EVIDENCE,
            confidence="insufficient",
            reason="SPARC requires positive sample duration",
        )

    # A higher (less negative) SPARC value is smoother. Normalization maps the
    # prototype v1 bounds into the common [0, 1] aggregation range.
    value = spectral_arc_length(samples, sample_rate=rate)
    return MetricValue(
        metric_id=metric_id,
        status=MetricStatus.COMPUTED,
        raw_value=value,
        normalized_score=normalize_higher_is_better(value, good=good, bad=bad),
        confidence="sufficient",
        units="spectral_arc_length",
        raw_inputs_summary={"sample_count": len(samples), "sample_rate_hz": rate},
    )


def spectral_arc_length(samples: Sequence[float], *, sample_rate: float) -> float:
    """Return raw SPARC; callers normalize according to metric-specific bounds."""
    magnitudes = _single_sided_magnitudes(samples)
    if len(magnitudes) < 2:
        return 0.0
    peak = max(magnitudes)
    if peak <= 0.0:
        return 0.0
    # SPARC operates on the spectrum shape, not absolute movement amplitude.
    normalized = [value / peak for value in magnitudes]
    freq_step = sample_rate / len(samples)
    cutoff_index = _adaptive_cutoff(normalized, freq_step=freq_step)
    cutoff_index = max(1, cutoff_index)
    max_freq = cutoff_index * freq_step
    if max_freq <= 0.0:
        return 0.0

    arc = 0.0
    prev_x = 0.0
    prev_y = normalized[0]
    for index in range(1, cutoff_index + 1):
        x = (index * freq_step) / max_freq
        y = normalized[index]
        arc += math.hypot(x - prev_x, y - prev_y)
        prev_x = x
        prev_y = y
    # SPARC is defined as negative arc length; smoother spectra have shorter
    # arcs and therefore values closer to zero.
    return -arc


def _single_sided_magnitudes(samples: Sequence[float]) -> list[float]:
    count = len(samples)
    centered = [float(sample) for sample in samples]
    magnitudes: list[float] = []
    for frequency_index in range(count // 2 + 1):
        # Explicit DFT keeps the library dependency-free. Metric inputs are
        # short episode summaries, so clarity is preferable to a mandatory FFT
        # dependency at this layer.
        coefficient = sum(
            value * cmath.exp(-2j * math.pi * frequency_index * sample_index / count)
            for sample_index, value in enumerate(centered)
        )
        magnitudes.append(abs(coefficient))
    return magnitudes


def _adaptive_cutoff(
    normalized_magnitudes: Sequence[float],
    *,
    freq_step: float,
    threshold: float = 0.05,
    max_frequency: float = 20.0,
) -> int:
    max_index = min(len(normalized_magnitudes) - 1, int(max_frequency / freq_step))
    for index in range(1, max_index + 1):
        # First frequency after which the normalized spectrum remains below the
        # SPARC tail threshold. If the tail never settles, use the capped band.
        if all(value < threshold for value in normalized_magnitudes[index + 1 : max_index + 1]):
            return index
    return max_index

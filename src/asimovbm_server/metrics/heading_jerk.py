"""Yaw-rate SPARC for heading jerk.

This metric applies the SPARC smoothness formula to robot yaw-rate samples.
Translational smoothness can miss abrupt swerves, so heading jerk is tracked as
a separate impression/safety feature.

References:
- Balasubramanian et al. (2012), "A Robust and Sensitive Metric for Quantifying
  Movement Smoothness" (SPARC applies to kinematic signals; spec source S25).
- Balasubramanian et al. (2018), SPARC-Gyro work using IMU yaw/pitch/roll for
  gait assessment (technical precedent for angular signals; spec source S26).
- Mavrogiannis et al. (2022), "Social Momentum" (jerky/ambiguous heading
  changes as observer-relevant failure mode; spec source S28).

Benchmark adaptation:
No cited HRI paper applies SPARC directly to robot yaw rate. This module is the
benchmark's straight extension of SPARC to angular velocity.
"""

from __future__ import annotations

from collections.abc import Sequence

from .conventions import DEFAULT_CONFIG
from .models import MetricValue
from .sparc import compute as compute_sparc


def compute(*, yaw_rates: Sequence[float], times: Sequence[float]) -> MetricValue:
    # Reuse the same spectral implementation as translational smoothness, but
    # keep metric-specific bounds and id so reports can separate the evidence.
    return compute_sparc(
        samples=yaw_rates,
        times=times,
        metric_id="heading_jerk",
        bad=DEFAULT_CONFIG.sparc_yaw_bad,
        good=DEFAULT_CONFIG.sparc_yaw_good,
    )

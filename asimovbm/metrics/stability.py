"""Stability from collision, invalid-action, and instability events.

This metric summarizes visible controlledness failures: falls or instability
events, collisions, and invalid actions. Collisions are intentionally counted
here even when they also cause task failure, because a human evaluator can form
both a competence judgment and an impression/safety judgment from the same
collision.

References:
- Dragan et al. (2013), "Legibility and Predictability of Robot Motion"
  (predictability/controlledness as perception-relevant motion quality; spec
  source S16).
- Schulz et al. (2020), velocity-profile/Godspeed HRI study (motion quality and
  subjective robot perception; spec source S17).
- Balasubramanian et al. (2015), "On the Analysis of Movement Smoothness"
  (general movement-quality prior; spec source S18).

Benchmark adaptation:
The event-count formula and `n_bad` threshold are v1 calibration choices, not
directly published stability equations.
"""

from __future__ import annotations

from .conventions import clip
from .models import MetricStatus, MetricValue


def compute(
    *,
    instability_events: int = 0,
    collisions: int = 0,
    invalid_actions: int = 0,
    n_bad: int = 3,
    exposes_stability_state: bool = True,
) -> MetricValue:
    # All three event types are behavioral evidence of poor controlledness.
    # They are not mutually exclusive with task failure metrics.
    total = instability_events + collisions + invalid_actions
    if n_bad <= 0:
        return MetricValue(
            metric_id="stability",
            status=MetricStatus.INVALID_INPUT,
            confidence="insufficient",
            reason="n_bad must be positive",
        )
    score = 1.0 - clip(total / n_bad)
    return MetricValue(
        metric_id="stability",
        status=MetricStatus.COMPUTED,
        raw_value=score,
        normalized_score=score,
        confidence="sufficient" if exposes_stability_state else "low",
        units="ratio",
        raw_inputs_summary={
            "instability_events": instability_events,
            "collisions": collisions,
            "invalid_actions": invalid_actions,
        },
    )

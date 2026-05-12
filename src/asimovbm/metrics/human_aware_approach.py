"""Human-aware approach with side/angle term.

This metric scores whether the robot made progress toward the target while
preserving bystander clearance and approaching the target from a socially
preferred front-side angle. The angle term rewards bearings around +/-45
degrees in the target's frame because the cited approach-direction studies
found frontal approaches uncomfortable and front-side approaches preferred.

References:
- Dautenhahn et al. (2006), "How May I Serve You? A Robot Companion
  Approaching a Seated Person in a Helping Context" (most participants rejected
  frontal approaches; spec source S06).
- Woods et al. (2006), "Methodological Issues in HRI: A Comparison of Live and
  Video-Based Methods in Robot-to-Human Approach Direction Trials" (front-left
  and front-right approaches preferred; spec source S07).
- Pacchierotti et al. (2005), "Human-Robot Embodied Interaction in Hallway
  Settings" (lateral distance/signaling priors; spec source S08).
- Neggers et al. (2022), "The Effect of Robot Speed on Comfortable Passing
  Distances" (comfort-distance prior; spec source S12).

Benchmark adaptation:
The score is an arithmetic blend of progress, bystander clearance, and approach
angle when those components are applicable. Missing optional terms are omitted
from the per-attempt mean rather than treated as failures.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from .conventions import clip, mean, normalize_higher_is_better
from .models import MetricStatus, MetricValue


@dataclass(frozen=True)
class HumanAwareApproachAttempt:
    start_distance_to_target: float
    final_distance_to_target: float
    bystander_clearance: float | None = None
    bearing_at_approach: float | None = None
    used_closest_approach_fallback: bool = False


def compute(*, attempts: Sequence[HumanAwareApproachAttempt]) -> MetricValue:
    if not attempts:
        return MetricValue(
            metric_id="human_aware_approach",
            status=MetricStatus.INSUFFICIENT_EVIDENCE,
            confidence="insufficient",
            reason="requires at least one approach attempt",
        )
    scores: list[float] = []
    fallback_count = 0
    for attempt in attempts:
        if attempt.start_distance_to_target <= 0.0:
            return MetricValue(
                metric_id="human_aware_approach",
                status=MetricStatus.INVALID_INPUT,
                confidence="insufficient",
                reason="start distance must be positive",
            )
        components = [
            clip(
                (attempt.start_distance_to_target - attempt.final_distance_to_target)
                / attempt.start_distance_to_target
            )
        ]
        # Optional components are omitted when the scenario cannot expose them
        # (for example, empty-room tiers have no bystander-clearance term).
        if attempt.bystander_clearance is not None:
            components.append(clip(attempt.bystander_clearance))
        if attempt.bearing_at_approach is not None:
            # Dautenhahn/Woods motivate front-side approach angles; exact
            # +/-45-degree scoring is the benchmark's v1 operationalization.
            preferred_error = min(
                abs(attempt.bearing_at_approach - math.pi / 4.0),
                abs(attempt.bearing_at_approach + math.pi / 4.0),
            )
            components.append(clip(1.0 - preferred_error / (math.pi / 2.0)))
        if attempt.used_closest_approach_fallback:
            fallback_count += 1
        scores.append(mean(components) or 0.0)
    raw = mean(scores) or 0.0
    return MetricValue(
        metric_id="human_aware_approach",
        status=MetricStatus.COMPUTED,
        raw_value=raw,
        normalized_score=normalize_higher_is_better(raw, good=0.9, bad=0.4),
        confidence="sufficient",
        units="ratio",
        raw_inputs_summary={"attempts": len(attempts), "closest_approach_fallbacks": fallback_count},
    )

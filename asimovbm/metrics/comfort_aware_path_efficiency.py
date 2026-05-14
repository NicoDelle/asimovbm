"""Comfort-aware path efficiency.

This metric is a social-navigation variant of ordinary path efficiency. Plain
`optimal_length / actual_length` can punish a robot for making the socially
correct detour around a person. This module therefore compares the actual path
length spent outside bystander comfort zones with a precomputed
comfort-respecting optimum. If an episode is successful but the robot spent
almost all of the approach inside comfort zones, the high-density guard clamps
that episode to zero rather than allowing a tiny denominator to look efficient.

References:
- Neggers et al. (2022), "The Effect of Robot Speed on Comfortable Passing
  Distances" (comfort distance saturation around roughly 0.9 m; spec sources
  S12/S29).
- Kruse et al. (2013), "Human-aware robot navigation: A survey" (socially
  acceptable navigation can trade off with efficiency; spec source S32).
- Mavrogiannis et al. (2023), "Core Challenges of Social Robot Navigation: A
  Survey" (path efficiency alone does not explain whether deviations were
  socially necessary; spec source S33).

Benchmark adaptation:
`optimal_outside_comfort` is supplied by the later scenario/extraction layer.
This pure function only scores already-extracted per-episode path summaries.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .conventions import EPS, clip, mean, normalize_higher_is_better
from .models import MetricStatus, MetricValue


@dataclass(frozen=True)
class PathEfficiencyAttempt:
    successful: bool
    actual_outside_comfort: float | None
    actual_total: float | None
    optimal_outside_comfort: float | None
    used_unconstrained_fallback: bool = False


def compute(*, attempts: Sequence[PathEfficiencyAttempt]) -> MetricValue:
    successful = [attempt for attempt in attempts if attempt.successful]
    if not successful:
        return MetricValue(
            metric_id="comfort_aware_path_efficiency",
            status=MetricStatus.NOT_APPLICABLE,
            confidence="not_applicable",
            reason="path efficiency is only computed for successful episodes",
        )

    per_episode: list[float] = []
    fallback_count = 0
    for attempt in successful:
        if (
            attempt.actual_outside_comfort is None
            or attempt.actual_total is None
            or attempt.optimal_outside_comfort is None
        ):
            return MetricValue(
                metric_id="comfort_aware_path_efficiency",
                status=MetricStatus.INSUFFICIENT_EVIDENCE,
                confidence="insufficient",
                reason="requires actual and optimal comfort-aware path lengths",
            )
        # If nearly all progress happened inside a bystander's comfort band, a
        # ratio against the tiny "outside comfort" denominator would be
        # misleadingly high. This guard preserves the intended failure mode.
        if attempt.actual_total > 0 and attempt.actual_outside_comfort / attempt.actual_total < 0.1:
            per_episode.append(0.0)
        else:
            # The optimum may be an unconstrained fallback when no
            # comfort-respecting path exists; preserve that count in the output
            # so reviewers can spot scenarios where the precomputed prior was
            # unavailable.
            per_episode.append(
                clip(attempt.optimal_outside_comfort / max(attempt.actual_outside_comfort, EPS))
            )
        if attempt.used_unconstrained_fallback:
            fallback_count += 1

    raw = mean(per_episode) or 0.0
    return MetricValue(
        metric_id="comfort_aware_path_efficiency",
        status=MetricStatus.COMPUTED,
        raw_value=raw,
        normalized_score=normalize_higher_is_better(raw, good=1.0, bad=0.35),
        confidence="sufficient" if len(successful) >= 3 else "insufficient",
        units="ratio",
        raw_inputs_summary={
            "successful_episodes": len(successful),
            "unconstrained_fallbacks": fallback_count,
        },
    )

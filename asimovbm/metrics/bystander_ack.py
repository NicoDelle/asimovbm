"""Bystander acknowledgement from lateral deviation and slowdown.

This metric asks whether the robot showed kinematic awareness of bystanders it
passed near. It uses two morphology-neutral signals: moving laterally away from
the bystander before the closest pass, and slowing down inside the near zone.
Closing distance after first detection is intentionally allowed to score below
the midpoint even if the robot slows down.

References:
- Mavrogiannis et al. (2022), "Social Momentum: Design and Evaluation of a
  Framework for Socially Competent Robot Navigation" (committed low-acceleration
  heading changes reduce human corrections; spec source S28).
- Kretzschmar et al. (2016), IJRR work on inverse reinforcement learning for
  mobile robot navigation (cooperative kinematic features; spec source S31).
- Watanabe et al. (2015), "Communicating Robotic Navigational Intentions"
  (deceleration as readable intent signal; spec source S13).

Benchmark adaptation:
The lateral-plus-slowdown blend is local to this benchmark; no single cited
paper defines exactly this combined bystander acknowledgement formula.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .conventions import DEFAULT_CONFIG, EPS, clip, mean, normalize_higher_is_better
from .models import MetricStatus, MetricValue


@dataclass(frozen=True)
class BystanderPass:
    distance_at_first_detection: float
    distance_at_pass: float
    speed_before_near_zone: float
    speed_inside_near_zone: float


def compute(
    *,
    passes: Sequence[BystanderPass],
    d_personal: float = DEFAULT_CONFIG.d_personal,
) -> MetricValue:
    if not passes:
        return MetricValue(
            metric_id="bystander_ack",
            status=MetricStatus.NOT_APPLICABLE,
            confidence="not_applicable",
            reason="no bystander entered the near-human zone",
        )
    scores: list[float] = []
    for bystander_pass in passes:
        # Signed lateral term is important: if the robot moves closer from first
        # detection to closest pass, that is a failure even when it decelerates.
        lateral_signed = (
            bystander_pass.distance_at_pass - bystander_pass.distance_at_first_detection
        ) / d_personal
        lateral_avoidance = clip(0.5 + 0.5 * lateral_signed)
        # Slowdown is normalized by pre-near-zone speed so a robot that was
        # already slow does not gain artificial credit.
        slowdown = clip(
            (bystander_pass.speed_before_near_zone - bystander_pass.speed_inside_near_zone)
            / max(bystander_pass.speed_before_near_zone, EPS)
        )
        scores.append(0.5 * lateral_avoidance + 0.5 * slowdown)
    raw = mean(scores) or 0.0
    return MetricValue(
        metric_id="bystander_ack",
        status=MetricStatus.COMPUTED,
        raw_value=raw,
        normalized_score=normalize_higher_is_better(raw, good=0.5, bad=0.05),
        confidence="sufficient",
        units="ratio",
        raw_inputs_summary={"bystander_passes": len(passes)},
    )

"""Acknowledgement clarity for the target human.

This metric checks whether the robot's declared forward or sensor-facing
direction enters the target cone before approach motion begins. It is intended
to be morphology-neutral: a wheeled robot, quadruped, or humanoid can satisfy
the metric by exposing a facing direction, without relying on a hard-coded
visual gesture vocabulary.

References:
- Pacchierotti et al. (2005), "Human-Robot Embodied Interaction in Hallway
  Settings" (early signaling distance was preferred and read as trustworthy;
  spec source S08).
- Watanabe et al. (2015), "Communicating Robotic Navigational Intentions"
  (intent communication; spec source S13).
- Palinko et al. (2020), "Intention Indication for Human Aware Robot
  Navigation" (turn and lighting cues; spec source S14).
- 2023 VR co-navigation visualization study, "Your Way Or My Way" (intent
  visualization and trust; spec source S15).

Benchmark adaptation:
Forward-axis metadata comes from the robot package. Missing metadata lowers
confidence instead of inventing a morphology-specific acknowledgement.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .conventions import DEFAULT_CONFIG
from .models import MetricStatus, MetricValue


@dataclass(frozen=True)
class AcknowledgementAttempt:
    min_bearing_error: float | None
    time_to_cone: float | None
    approach_start_time: float | None
    has_forward_axis: bool = True


def compute(
    *,
    attempts: Sequence[AcknowledgementAttempt],
    theta_ack: float = DEFAULT_CONFIG.theta_ack_rad,
    t_ack: float = DEFAULT_CONFIG.t_ack,
) -> MetricValue:
    if not attempts:
        return MetricValue(
            metric_id="acknowledgement_clarity",
            status=MetricStatus.NOT_APPLICABLE,
            confidence="not_applicable",
            reason="no acknowledgement opportunities were present",
        )
    scores: list[bool] = []
    low_confidence = False
    for attempt in attempts:
        if not attempt.has_forward_axis:
            low_confidence = True
        # Facing after the robot has already begun approaching is too late to
        # count as acknowledgement; the cue has to precede approach motion.
        scores.append(
            attempt.min_bearing_error is not None
            and attempt.min_bearing_error <= theta_ack
            and attempt.time_to_cone is not None
            and attempt.time_to_cone <= t_ack
            and (
                attempt.approach_start_time is None
                or attempt.time_to_cone <= attempt.approach_start_time
            )
        )
    raw = sum(scores) / len(scores)
    return MetricValue(
        metric_id="acknowledgement_clarity",
        status=MetricStatus.COMPUTED,
        raw_value=raw,
        normalized_score=raw,
        confidence="low" if low_confidence else "sufficient",
        units="ratio",
        raw_inputs_summary={"attempts": len(attempts), "successes": sum(scores)},
    )

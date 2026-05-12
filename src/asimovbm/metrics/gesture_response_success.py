"""Gesture response success after a structured come-here event.

This metric evaluates behavior after the benchmark emits a structured
`come_here` task event. It does not attempt gesture recognition from pixels or
raw skeleton data. A response succeeds only when the robot starts toward the
target within the acknowledgement window and does not first move toward a
non-target human.

References:
- Watanabe et al. (2015), "Communicating Robotic Navigational Intentions"
  (intent communication improves legibility and human motion; spec source S13).
- Palinko et al. (2020), "Intention Indication for Human Aware Robot
  Navigation" (turn gesture and lighting cues affect motion prediction; spec
  source S14).
- 2023 VR co-navigation visualization study, "Your Way Or My Way" (robot
  intent/pedestrian prediction visualizations improved trust; spec source S15).

Benchmark adaptation:
The benchmark supplies already-structured event outcomes. This module measures
response correctness, not perception or recognition of the human's gesture.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .conventions import DEFAULT_CONFIG
from .models import MetricStatus, MetricValue


@dataclass(frozen=True)
class GestureResponseAttempt:
    has_event: bool
    response_time: float | None
    moved_toward_target: bool
    moved_toward_non_target_first: bool = False


def compute(
    *,
    attempts: Sequence[GestureResponseAttempt],
    t_ack: float = DEFAULT_CONFIG.t_ack,
) -> MetricValue:
    applicable = [attempt for attempt in attempts if attempt.has_event]
    if not applicable:
        return MetricValue(
            metric_id="gesture_response_success",
            status=MetricStatus.NOT_APPLICABLE,
            confidence="not_applicable",
            reason="no come_here events were present",
        )
    # The "non-target first" guard is what distinguishes target understanding
    # from merely moving after a cue.
    successes = [
        attempt.response_time is not None
        and attempt.response_time <= t_ack
        and attempt.moved_toward_target
        and not attempt.moved_toward_non_target_first
        for attempt in applicable
    ]
    raw = sum(successes) / len(successes)
    return MetricValue(
        metric_id="gesture_response_success",
        status=MetricStatus.COMPUTED,
        raw_value=raw,
        normalized_score=raw,
        confidence="sufficient",
        units="ratio",
        raw_inputs_summary={"events": len(applicable), "successes": sum(successes)},
    )

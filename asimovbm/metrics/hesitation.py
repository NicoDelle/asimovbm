"""Hesitation-rate metric.

This metric counts stop-and-go and reversal episodes that suggest the robot is
stuck, indecisive, or locally oscillating. It deliberately separates two cases
that look similar in speed traces: social yielding near a bystander is excluded
through `yielding_mask`, while non-social stopping before goal completion is
counted. Reversals are also displacement-gated so brief heading overshoots do
not become false positives.

References:
- Trautman and Krause (2010), "Unfreezing the Robot: Navigation in Dense,
  Interacting Crowds" (freezing robot problem; spec source S22).
- Trautman et al. (2015), IJRR work on robot navigation in dense human crowds
  (quantified freezing behavior; spec source S23).
- Steinfeld et al. (2006), "Common Metrics for Human-Robot Interaction"
  (interventions-per-time style navigation quality proxy; spec source S24).
- Mavrogiannis et al. (2023), "Core Challenges of Social Robot Navigation: A
  Survey" (path irregularity and unnecessary rotation; spec source S33).

Benchmark adaptation:
The exact `events / duration` hesitation rate is a local operationalization of
the cited freezing/intervention ideas; there is no canonical published
hesitation-rate formula for this benchmark.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from .conventions import (
    DEFAULT_CONFIG,
    angle_error,
    contiguous_true_epochs,
    integrate_time_series,
    normalize_lower_is_better,
)
from .models import MetricStatus, MetricValue


def compute(
    *,
    times: Sequence[float],
    speeds: Sequence[float],
    headings: Sequence[float],
    target_bearings: Sequence[float],
    yielding_mask: Sequence[bool] | None = None,
    goal_reached_mask: Sequence[bool] | None = None,
    v_hes: float = DEFAULT_CONFIG.v_hes,
    dt_hes: float = DEFAULT_CONFIG.dt_hes,
    d_reversal_min: float = DEFAULT_CONFIG.d_reversal_min,
) -> MetricValue:
    lengths = {len(times), len(speeds), len(headings), len(target_bearings)}
    if len(lengths) != 1:
        return MetricValue(
            metric_id="hesitation",
            status=MetricStatus.INVALID_INPUT,
            confidence="insufficient",
            reason="times, speeds, headings, and target bearings must align",
        )
    if len(times) < 2 or times[-1] - times[0] < 2 * dt_hes:
        return MetricValue(
            metric_id="hesitation",
            status=MetricStatus.INSUFFICIENT_EVIDENCE,
            confidence="insufficient",
            reason="episode duration is too short to evaluate hesitation",
        )
    yielding = list(yielding_mask or [False] * len(times))
    reached = list(goal_reached_mask or [False] * len(times))
    if len(yielding) != len(times) or len(reached) != len(times):
        return MetricValue(
            metric_id="hesitation",
            status=MetricStatus.INVALID_INPUT,
            confidence="insufficient",
            reason="mask lengths must match times",
        )

    # A zero-speed segment is only hesitation if it is neither social yielding
    # nor post-success settling. The extraction layer owns those masks.
    stop_mask = [
        abs(speed) < v_hes and not is_yielding and not is_reached
        for speed, is_yielding, is_reached in zip(speeds, yielding, reached, strict=True)
    ]
    hesitation_epochs = [
        epoch for epoch in contiguous_true_epochs(times, stop_mask) if epoch[1] - epoch[0] >= dt_hes
    ]

    # Reversal captures moving away from the target, not simply rotating in
    # place. The later displacement gate removes tiny orientation glitches.
    reversal_mask = [
        math.cos(heading - bearing) < 0.0 and abs(speed) > v_hes and not is_reached
        for heading, bearing, speed, is_reached in zip(
            headings,
            target_bearings,
            speeds,
            reached,
            strict=True,
        )
    ]
    reversal_epochs = []
    for start, end in contiguous_true_epochs(times, reversal_mask):
        indices = [index for index, time in enumerate(times) if start <= time <= end]
        if len(indices) < 2 or end - start < dt_hes:
            continue
        distance = integrate_time_series(
            [times[index] for index in indices],
            [abs(speeds[index]) for index in indices],
        )
        if distance >= d_reversal_min:
            reversal_epochs.append((start, end))

    # Normalizing by episode duration makes a short burst of indecision more
    # severe in a short episode than the same burst in a long episode.
    event_count = len(hesitation_epochs) + len(reversal_epochs)
    duration = times[-1] - times[0]
    rate = event_count / duration
    return MetricValue(
        metric_id="hesitation",
        status=MetricStatus.COMPUTED,
        raw_value=rate,
        normalized_score=normalize_lower_is_better(rate, good=0.0, bad=0.5),
        confidence="sufficient",
        units="events/s",
        raw_inputs_summary={
            "hesitation_epochs": len(hesitation_epochs),
            "reversal_epochs": len(reversal_epochs),
            "max_heading_error": max(
                angle_error(heading, bearing)
                for heading, bearing in zip(headings, target_bearings, strict=True)
            ),
        },
    )

"""Task completion time for successful social-navigation episodes.

This metric measures efficiency only after behavioral success is established.
Failed episodes are excluded because their duration is already accounted for by
`task_success_rate`; mixing failures into completion time would double-penalize
the same failure mode and make "never finished" indistinguishable from "slow
but successful."

References:
- Francis et al. (2023), "Principles and Guidelines for Evaluating Social Robot
  Navigation" (evaluation guidance that treats efficiency as a recognized but
  secondary social-navigation criterion; spec source S19).

Benchmark adaptation:
The good threshold is set to 35% of the scenario timeout and the bad threshold
to the full timeout. Those constants are v1 calibration defaults, not claims
from Francis et al.
"""

from __future__ import annotations

from collections.abc import Sequence

from .conventions import DEFAULT_CONFIG, mean, normalize_lower_is_better
from .models import MetricStatus, MetricValue


def compute(
    *,
    successful_durations: Sequence[float],
    t_max: float = DEFAULT_CONFIG.t_max,
) -> MetricValue:
    # Completion time is intentionally not applicable when there are no
    # successes. A missing successful episode is not a slow completion time.
    duration = mean(successful_durations)
    if duration is None:
        return MetricValue(
            metric_id="task_completion_time",
            status=MetricStatus.NOT_APPLICABLE,
            confidence="not_applicable",
            reason="no successful valid episodes",
        )
    good = 0.35 * t_max
    return MetricValue(
        metric_id="task_completion_time",
        status=MetricStatus.COMPUTED,
        raw_value=duration,
        normalized_score=normalize_lower_is_better(duration, good=good, bad=t_max),
        confidence="sufficient",
        units="s",
        raw_inputs_summary={"successful_episodes": len(successful_durations)},
    )

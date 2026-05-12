"""Robot speed near humans using the 95th percentile.

This metric captures fast motion while the robot is close to people. It uses a
95th percentile rather than a mean because human safety perception is usually
driven by the fastest close pass, not by the average speed over a mostly calm
episode.

References:
- Pacchierotti et al. (2005), "Human-Robot Embodied Interaction in Hallway
  Settings" (speed, signaling distance, and lateral distance shape comfort;
  spec source S08).
- Neggers et al. (2022), "The Effect of Robot Speed on Comfortable Passing
  Distances" (higher speed lowers comfort; spec sources S12/S29).
- Story et al. (2022), "Do Speed and Proximity Affect Human-Robot
  Collaboration with an Industrial Robot Arm?" (speed/proximity safety prior
  outside mobile navigation; spec source S21).

Benchmark adaptation:
The p95 statistic and the 0.25 m/s to 1.0 m/s normalization band are v1
benchmark choices. The cited papers motivate speed-near-people as safety and
comfort evidence, while this module fixes a robust worst-case summary.
"""

from __future__ import annotations

from collections.abc import Sequence

from .conventions import DEFAULT_CONFIG, normalize_lower_is_better, percentile
from .models import MetricStatus, MetricValue


def compute(
    *,
    speeds: Sequence[float],
    min_human_distances: Sequence[float],
    d_near: float = DEFAULT_CONFIG.d_near,
) -> MetricValue:
    if len(speeds) != len(min_human_distances):
        return MetricValue(
            metric_id="speed_near_humans_p95",
            status=MetricStatus.INVALID_INPUT,
            confidence="insufficient",
            reason="speed and distance streams must align",
        )
    # Only samples inside the near-human zone matter. If the robot never enters
    # that zone, the metric is not applicable rather than a perfect score.
    near_speeds = [
        abs(speed)
        for speed, min_distance in zip(speeds, min_human_distances, strict=True)
        if min_distance < d_near
    ]
    raw = percentile(near_speeds, 95.0)
    if raw is None:
        return MetricValue(
            metric_id="speed_near_humans_p95",
            status=MetricStatus.NOT_APPLICABLE,
            confidence="not_applicable",
            reason="robot never entered the near-human zone",
        )
    return MetricValue(
        metric_id="speed_near_humans_p95",
        status=MetricStatus.COMPUTED,
        raw_value=raw,
        normalized_score=normalize_lower_is_better(raw, good=0.25, bad=1.0),
        confidence="sufficient",
        units="m/s",
        raw_inputs_summary={"near_zone_samples": len(near_speeds)},
    )

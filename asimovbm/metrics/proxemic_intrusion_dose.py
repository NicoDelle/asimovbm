"""Depth-weighted proxemic intrusion dose.

This metric integrates how deeply and how long the robot enters human personal
space. It replaces a binary "time inside threshold" metric because human
discomfort should distinguish a shallow brush against the boundary from a very
close pass. The raw unit is meter-seconds: intrusion depth multiplied by time.

References:
- Takayama and Pantofaru (2009), "Influences on Proxemic Behaviors in
  Human-Robot Interaction" (proxemic distance effects; spec source S10).
- Mumm and Mutlu (2011), "Human-Robot Proxemics" (distance, gaze, and
  likeability effects; spec source S11).
- Neggers et al. (2022), "The Effect of Robot Speed on Comfortable Passing
  Distances" (depth-sensitive comfort response; spec sources S12/S29).
- Rios-Martinez et al. (2015), "A survey on human aware robot navigation"
  (zone-based proxemic formulations; spec source S30).
- Mavrogiannis et al. (2023), "Core Challenges of Social Robot Navigation: A
  Survey" (social-navigation context; spec source S33).

Benchmark adaptation:
The depth integral is the benchmark's local improvement over binary proxemic
time. The spec notes adjacent prior art in conflict-intensity metrics from
autonomous driving, but no single cited HRI paper defines this exact dose.
"""

from __future__ import annotations

from collections.abc import Sequence

from .conventions import DEFAULT_CONFIG, distance, integrate_time_series, normalize_lower_is_better
from .models import MetricStatus, MetricValue


def compute(
    *,
    times: Sequence[float],
    robot_positions: Sequence[tuple[float, float]],
    human_positions: Sequence[Sequence[tuple[float, float]]],
    d_personal: float = DEFAULT_CONFIG.d_personal,
    bystanders_present: bool = True,
) -> MetricValue:
    if len(times) != len(robot_positions) or len(times) != len(human_positions):
        return MetricValue(
            metric_id="proxemic_intrusion_dose",
            status=MetricStatus.INVALID_INPUT,
            confidence="insufficient",
            reason="times, robot positions, and human positions must align",
        )
    if len(times) < 2:
        return MetricValue(
            metric_id="proxemic_intrusion_dose",
            status=MetricStatus.INSUFFICIENT_EVIDENCE,
            confidence="insufficient",
            reason="requires at least two samples",
        )
    depths: list[float] = []
    for robot, humans in zip(robot_positions, human_positions, strict=True):
        if not humans:
            depths.append(0.0)
            continue
        # At each frame, only the nearest human determines the intrusion depth;
        # this keeps the dose aligned with "closest uncomfortable encounter"
        # rather than multiplying by crowd size.
        min_distance = min(distance(robot, human) for human in humans)
        depths.append(max(0.0, d_personal - min_distance))
    dose = integrate_time_series(times, depths)
    duration = times[-1] - times[0]
    # Bad bound: equivalent to spending 25% of the episode at full personal
    # space intrusion depth. Scenario calibration can change this constant.
    bad = d_personal * 0.25 * duration
    if bad <= 0.0:
        return MetricValue(
            metric_id="proxemic_intrusion_dose",
            status=MetricStatus.INSUFFICIENT_EVIDENCE,
            confidence="insufficient",
            reason="requires positive episode duration",
        )
    return MetricValue(
        metric_id="proxemic_intrusion_dose",
        status=MetricStatus.COMPUTED,
        raw_value=dose,
        normalized_score=normalize_lower_is_better(dose, good=0.0, bad=bad),
        confidence="sufficient",
        units="m*s",
        raw_inputs_summary={
            "duration_s": duration,
            "bystander_intrusion_applicable": bystanders_present,
        },
    )

"""Minimum human-robot distance.

This metric reports the closest physical spacing between the robot and any
human during a valid behavioral episode. It is a simple worst-case safety
feature: one close pass is enough to reduce the score, even if the rest of the
trajectory is comfortable.

References:
- Dautenhahn et al. (2006), "How May I Serve You? A Robot Companion
  Approaching a Seated Person in a Helping Context" (approach comfort and
  proxemics; spec source S06).
- Pacchierotti et al. (2006), "Evaluation of Distance for Passage for a Social
  Robot" (passing-distance comfort; spec source S09).
- Takayama and Pantofaru (2009), "Influences on Proxemic Behaviors in
  Human-Robot Interaction" (comfortable robot-human distances; spec source S10).
- Mumm and Mutlu (2011), "Human-Robot Proxemics" (physical and psychological
  distancing; spec source S11).
- Neggers et al. (2022), "The Effect of Robot Speed on Comfortable Passing
  Distances" (comfort-distance curve; spec sources S12/S29).

Benchmark adaptation:
The hard floor and personal-space thresholds are v1 calibration constants. The
metric uses the cited proxemics literature for direction and construct
validity, while the exact numeric bounds live in scenario config.
"""

from __future__ import annotations

from collections.abc import Sequence

from .conventions import DEFAULT_CONFIG, distance, normalize_higher_is_better
from .models import MetricStatus, MetricValue


def compute(
    *,
    robot_positions: Sequence[tuple[float, float]],
    human_positions: Sequence[Sequence[tuple[float, float]]],
    d_hard: float = DEFAULT_CONFIG.d_hard,
    d_personal: float = DEFAULT_CONFIG.d_personal,
) -> MetricValue:
    if len(robot_positions) != len(human_positions):
        return MetricValue(
            metric_id="min_human_robot_distance",
            status=MetricStatus.INVALID_INPUT,
            confidence="insufficient",
            reason="robot and human streams must have the same length",
        )
    # Flatten all humans across all frames; this metric intentionally takes the
    # global minimum rather than an average because a single near collision is
    # the salient safety event.
    distances = [
        distance(robot, human)
        for robot, humans in zip(robot_positions, human_positions, strict=True)
        for human in humans
    ]
    if not distances:
        return MetricValue(
            metric_id="min_human_robot_distance",
            status=MetricStatus.NOT_APPLICABLE,
            confidence="not_applicable",
            reason="no humans present in the episode",
        )
    raw = min(distances)
    return MetricValue(
        metric_id="min_human_robot_distance",
        status=MetricStatus.COMPUTED,
        raw_value=raw,
        normalized_score=normalize_higher_is_better(raw, good=d_personal, bad=d_hard),
        confidence="sufficient",
        units="m",
        raw_inputs_summary={"sample_count": len(robot_positions)},
    )

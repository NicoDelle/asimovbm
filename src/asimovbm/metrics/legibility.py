"""Commit-time legibility proxy.

This metric estimates how early the robot's trajectory commits to the target
direction. It is a cheap trajectory-log proxy for Dragan-style legibility:
instead of running a full inverse-planning posterior, it finds the first
heading window that stays inside a target cone, then discounts by how much of
the post-commit trajectory remains inside that cone.

References:
- Dragan et al. (2013), "Legibility and Predictability of Robot Motion"
  (canonical legibility/predictability formulation; spec source S16).
- Mavrogiannis et al. (2022), "Social Momentum" (committed trajectory heading
  and reduced topological ambiguity; spec source S28).
- Mavrogiannis et al. (2023), "Core Challenges of Social Robot Navigation: A
  Survey" (social-navigation legibility context; spec source S33).

Benchmark adaptation:
The commit-time fractional-coverage score is local to this benchmark and should
be described as a proxy for, not a replacement of, Dragan et al.'s full
legibility model.
"""

from __future__ import annotations

from collections.abc import Sequence

from .conventions import DEFAULT_CONFIG, normalize_higher_is_better
from .models import MetricStatus, MetricValue


def compute(
    *,
    times: Sequence[float],
    heading_errors: Sequence[float],
    theta_commit: float = DEFAULT_CONFIG.commit_cone_rad,
    dt_commit: float = DEFAULT_CONFIG.dt_commit,
) -> MetricValue:
    if len(times) != len(heading_errors):
        return MetricValue(
            metric_id="legibility",
            status=MetricStatus.INVALID_INPUT,
            confidence="insufficient",
            reason="times and heading errors must align",
        )
    if len(times) < 2:
        return MetricValue(
            metric_id="legibility",
            status=MetricStatus.INSUFFICIENT_EVIDENCE,
            confidence="insufficient",
            reason="requires a target-defined trajectory",
        )
    duration = times[-1] - times[0]
    if duration <= 0:
        return MetricValue(
            metric_id="legibility",
            status=MetricStatus.INSUFFICIENT_EVIDENCE,
            confidence="insufficient",
            reason="requires positive episode duration",
        )

    commit_time = duration
    for index, time in enumerate(times):
        window_end = time + dt_commit
        # We only need a contiguous hold window, not commitment until the end of
        # the episode. Later excursions are discounted by fractional coverage.
        window = [
            abs(error)
            for sample_time, error in zip(times[index:], heading_errors[index:], strict=True)
            if sample_time <= window_end
        ]
        if window and times[-1] >= window_end and all(error <= theta_commit for error in window):
            commit_time = time - times[0]
            break

    if commit_time >= duration:
        raw = 0.0
        fraction_inside = 0.0
    else:
        # Post-commit coverage prevents a single early aligned frame from
        # looking legible when the remaining path is mostly ambiguous.
        post_errors = [
            abs(error)
            for sample_time, error in zip(times, heading_errors, strict=True)
            if sample_time >= times[0] + commit_time
        ]
        fraction_inside = (
            sum(1 for error in post_errors if error <= theta_commit) / len(post_errors)
            if post_errors
            else 0.0
        )
        raw = (1.0 - commit_time / duration) * fraction_inside

    return MetricValue(
        metric_id="legibility",
        status=MetricStatus.COMPUTED,
        raw_value=raw,
        normalized_score=normalize_higher_is_better(raw, good=0.7, bad=0.1),
        confidence="sufficient",
        units="ratio",
        raw_inputs_summary={
            "t_commit": commit_time,
            "fraction_inside_cone_post_commit": fraction_inside,
        },
    )

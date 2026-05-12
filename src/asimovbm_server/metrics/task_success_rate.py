"""Task success rate for social-navigation episodes.

This metric answers the simplest behavioral question: did the robot complete
the social-navigation task under the scenario's success contract? An attempt
counts as successful only when the target was acknowledged, the terminal state
is successful, the final target distance is inside the approved stop band, and
the stop happened before the scenario timeout. Technical failures should be
filtered out before this library function is called; the remaining attempts are
valid behavioral evidence.

References:
- Bartneck et al. (2009), "Measurement Instruments for the Anthropomorphism,
  Animacy, Likeability, Perceived Intelligence, and Perceived Safety of Robots"
  (Godspeed perceived-intelligence construct; spec source S01).
- Carpinella et al. (2017), "The Robotic Social Attributes Scale" (RoSAS
  competence construct; spec source S02).

Benchmark adaptation:
The success predicate itself is local to this benchmark. The cited papers
justify the latent competence/dexterity axis, while this module operationalizes
task success as one observable proxy for that axis.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .conventions import DEFAULT_CONFIG
from .models import MetricStatus, MetricValue


@dataclass(frozen=True)
class TaskSuccessAttempt:
    acknowledged: bool
    final_distance: float | None
    stop_time: float | None
    terminal_state: str


def compute(
    *,
    attempts: Sequence[TaskSuccessAttempt],
    d_stop_min: float = DEFAULT_CONFIG.d_stop_min,
    d_stop_max: float = DEFAULT_CONFIG.d_stop_max,
    t_max: float = DEFAULT_CONFIG.t_max,
) -> MetricValue:
    if not attempts:
        return MetricValue(
            metric_id="task_success_rate",
            status=MetricStatus.INSUFFICIENT_EVIDENCE,
            confidence="insufficient",
            reason="requires at least one valid behavioral episode",
        )
    # Each valid behavioral episode is evidence, including behavioral failures.
    # Do not drop failed attempts here; task-success rate is the metric that
    # converts them into zeros.
    successes = [_success(attempt, d_stop_min, d_stop_max, t_max) for attempt in attempts]
    rate = sum(1 for success in successes if success) / len(successes)
    confidence = "sufficient" if len(attempts) >= 3 else "insufficient"
    return MetricValue(
        metric_id="task_success_rate",
        status=MetricStatus.COMPUTED,
        raw_value=rate,
        normalized_score=rate,
        confidence=confidence,
        units="ratio",
        raw_inputs_summary={"valid_episodes": len(attempts), "successes": sum(successes)},
    )


def _success(
    attempt: TaskSuccessAttempt,
    d_stop_min: float,
    d_stop_max: float,
    t_max: float,
) -> bool:
    # Keep the predicate deliberately conjunctive. A robot that merely reaches
    # the distance band without acknowledging the target, or times out after a
    # correct stop, should not be counted as socially successful.
    return (
        attempt.acknowledged
        and attempt.terminal_state == "success"
        and attempt.final_distance is not None
        and d_stop_min <= attempt.final_distance <= d_stop_max
        and attempt.stop_time is not None
        and attempt.stop_time <= t_max
    )

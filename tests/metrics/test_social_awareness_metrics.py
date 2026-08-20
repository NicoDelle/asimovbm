from __future__ import annotations

import math

from asimovbm.metrics import MetricStatus
from asimovbm.metrics.acknowledgement_clarity import (
    AcknowledgementAttempt,
)
from asimovbm.metrics.acknowledgement_clarity import (
    compute as compute_ack,
)
from asimovbm.metrics.bystander_ack import BystanderPass
from asimovbm.metrics.bystander_ack import compute as compute_bystander_ack
from asimovbm.metrics.gesture_response_success import (
    GestureResponseAttempt,
)
from asimovbm.metrics.gesture_response_success import (
    compute as compute_gesture,
)
from asimovbm.metrics.human_aware_approach import (
    HumanAwareApproachAttempt,
)
from asimovbm.metrics.human_aware_approach import (
    compute as compute_human_aware,
)


def test_gesture_response_fails_when_non_target_is_approached_first() -> None:
    result = compute_gesture(
        attempts=[
            GestureResponseAttempt(True, 1.0, moved_toward_target=True),
            GestureResponseAttempt(True, 1.0, moved_toward_target=True, moved_toward_non_target_first=True),
        ]
    )

    assert result.status == MetricStatus.COMPUTED
    assert result.raw_value == 0.5


def test_gesture_response_not_applicable_without_event() -> None:
    result = compute_gesture(attempts=[GestureResponseAttempt(False, None, False)])

    assert result.status == MetricStatus.NOT_APPLICABLE


def test_acknowledgement_clarity_requires_facing_before_approach() -> None:
    result = compute_ack(
        attempts=[
            AcknowledgementAttempt(min_bearing_error=0.1, time_to_cone=1.0, approach_start_time=2.0),
            AcknowledgementAttempt(min_bearing_error=0.1, time_to_cone=3.5, approach_start_time=2.0),
        ]
    )

    assert result.raw_value == 0.5


def test_human_aware_approach_front_side_scores_better_than_frontal() -> None:
    front_side = compute_human_aware(
        attempts=[
            HumanAwareApproachAttempt(4.0, 1.0, bystander_clearance=1.0, bearing_at_approach=math.pi / 4.0)
        ]
    )
    frontal = compute_human_aware(
        attempts=[
            HumanAwareApproachAttempt(4.0, 1.0, bystander_clearance=1.0, bearing_at_approach=0.0)
        ]
    )

    assert front_side.raw_value > frontal.raw_value


def test_human_aware_approach_omits_empty_room_bystander_term() -> None:
    result = compute_human_aware(
        attempts=[HumanAwareApproachAttempt(4.0, 1.0, bystander_clearance=None, bearing_at_approach=math.pi / 4.0)]
    )

    assert result.status == MetricStatus.COMPUTED
    assert result.raw_inputs_summary["attempts"] == 1


def test_bystander_ack_scores_closing_distance_below_midpoint_even_with_slowdown() -> None:
    result = compute_bystander_ack(
        passes=[
            BystanderPass(
                distance_at_first_detection=2.0,
                distance_at_pass=0.8,
                speed_before_near_zone=1.0,
                speed_inside_near_zone=0.5,
            )
        ]
    )

    assert result.status == MetricStatus.COMPUTED
    assert result.raw_value < 0.5


def test_bystander_ack_not_applicable_without_near_passes() -> None:
    result = compute_bystander_ack(passes=[])

    assert result.status == MetricStatus.NOT_APPLICABLE

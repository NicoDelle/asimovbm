"""Placeholder metric registry for the social-navigation contract."""

from __future__ import annotations

from collections.abc import Iterable

from asimovbm_server.traces import EpisodeTrace

from .models import MetricContext, MetricFunction, MetricStatus, MetricValue

SOCIAL_NAVIGATION_METRIC_IDS: tuple[str, ...] = (
    "task_success_rate",
    "task_completion_time",
    "path_efficiency",
    "minimum_human_robot_distance",
    "proxemic_intrusion_time",
    "robot_speed_near_humans",
    "gesture_response_success",
    "acknowledgement_clarity",
    "human_aware_approach",
    "motion_smoothness_sparc",
    "stability_controlledness",
    "morphology_task_fit",
)


class PlaceholderMetricFunction:
    def __init__(
        self,
        metric_id: str,
        *,
        required_fields: tuple[str, ...] = ("steps",),
    ) -> None:
        self.id = metric_id
        self.required_fields = required_fields

    def compute(self, trace: EpisodeTrace, context: MetricContext) -> MetricValue:
        missing = _missing_required_fields(trace, self.required_fields)
        if missing:
            return MetricValue(
                metric_id=self.id,
                status=MetricStatus.INSUFFICIENT_EVIDENCE,
                reason=f"missing required trace fields: {', '.join(missing)}",
            )
        return MetricValue(
            metric_id=self.id,
            status=MetricStatus.NOT_IMPLEMENTED,
            reason="metric formula module not implemented yet",
            metadata={"tier_id": context.tier_id, "episode_id": context.episode_id},
        )


class MetricRegistry:
    def __init__(self, functions: Iterable[MetricFunction] = ()) -> None:
        self._functions: dict[str, MetricFunction] = {}
        for function in functions:
            self.register(function)

    def register(self, function: MetricFunction) -> None:
        self._functions[function.id] = function

    @property
    def metric_ids(self) -> tuple[str, ...]:
        return tuple(self._functions)

    def compute(self, trace: EpisodeTrace) -> dict[str, MetricValue]:
        context = MetricContext(tier_id=trace.tier_id, episode_id=trace.episode_id)
        return {
            metric_id: function.compute(trace, context)
            for metric_id, function in self._functions.items()
        }


def default_metric_registry() -> MetricRegistry:
    return MetricRegistry(
        PlaceholderMetricFunction(metric_id)
        for metric_id in SOCIAL_NAVIGATION_METRIC_IDS
    )


def _missing_required_fields(trace: EpisodeTrace, required_fields: tuple[str, ...]) -> list[str]:
    missing: list[str] = []
    for field in required_fields:
        value = getattr(trace, field, None)
        if value is None or value == ():
            missing.append(field)
    return missing

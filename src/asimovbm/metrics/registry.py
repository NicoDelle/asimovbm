"""Metric registry for the social-navigation contract.

The registry is kept for callers that need a stable list of metric ids. The
local runner uses :mod:`asimovbm.local_runner.metrics_bridge` for real formula
extraction because each formula accepts specific typed inputs rather than a raw
trace object.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .models import (
    SOCIAL_NAVIGATION_METRIC_IDS,
    MetricContext,
    MetricFunction,
    MetricStatus,
    MetricValue,
)


class TraceMetricFunction:
    """Runner-facing compatibility adapter until full trace extraction lands."""

    def __init__(
        self,
        metric_id: str,
        *,
        required_fields: tuple[str, ...] = ("steps",),
    ) -> None:
        self.id = metric_id
        self.required_fields = required_fields

    def compute(self, trace: Any, context: MetricContext) -> MetricValue:
        missing = _missing_required_fields(trace, self.required_fields)
        if missing:
            return MetricValue(
                metric_id=self.id,
                status=MetricStatus.INSUFFICIENT_EVIDENCE,
                confidence="insufficient",
                reason=f"missing required trace fields: {', '.join(missing)}",
                raw_inputs_summary={"missing_fields": tuple(missing)},
            )
        return MetricValue(
            metric_id=self.id,
            status=MetricStatus.INSUFFICIENT_EVIDENCE,
            confidence="insufficient",
            reason="metric extraction for v1 formula inputs is not implemented yet",
            raw_inputs_summary={
                "available_steps": len(trace.steps),
                "trace_adapter": "pending",
            },
            metadata={"tier_id": context.tier_id, "episode_id": context.episode_id},
        )


PlaceholderMetricFunction = TraceMetricFunction


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

    def compute(self, trace: Any) -> dict[str, MetricValue]:
        context = MetricContext(
            tier_id=getattr(trace, "tier_id", "local_validation"),
            episode_id=getattr(trace, "episode_id", "unknown"),
        )
        return {
            metric_id: function.compute(trace, context)
            for metric_id, function in self._functions.items()
        }


def default_metric_registry() -> MetricRegistry:
    return MetricRegistry(
        TraceMetricFunction(metric_id)
        for metric_id in SOCIAL_NAVIGATION_METRIC_IDS
    )


def _missing_required_fields(trace: Any, required_fields: tuple[str, ...]) -> list[str]:
    missing: list[str] = []
    for field in required_fields:
        value = getattr(trace, field, None)
        if value is None or value == ():
            missing.append(field)
    return missing

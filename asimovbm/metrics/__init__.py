"""Metric interfaces for social-navigation validation."""

from .aggregation import AxisScore, aggregate_axes
from .models import (
    SOCIAL_NAVIGATION_AXIS_IDS,
    SOCIAL_NAVIGATION_METRIC_IDS,
    MetricContext,
    MetricFunction,
    MetricStatus,
    MetricValue,
)
from .registry import (
    LocalTraceMetricFunction,
    MetricRegistry,
    default_metric_registry,
)

METRIC_SPEC_PATH = "docs/specs/social-navigation-metrics.md"

__all__ = [
    "METRIC_SPEC_PATH",
    "SOCIAL_NAVIGATION_AXIS_IDS",
    "SOCIAL_NAVIGATION_METRIC_IDS",
    "AxisScore",
    "MetricContext",
    "MetricFunction",
    "MetricRegistry",
    "MetricStatus",
    "MetricValue",
    "LocalTraceMetricFunction",
    "aggregate_axes",
    "default_metric_registry",
]

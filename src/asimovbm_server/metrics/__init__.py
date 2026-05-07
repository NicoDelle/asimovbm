"""Metric interfaces for social-navigation validation."""

from .models import MetricContext, MetricFunction, MetricStatus, MetricValue
from .registry import (
    SOCIAL_NAVIGATION_METRIC_IDS,
    MetricRegistry,
    PlaceholderMetricFunction,
    default_metric_registry,
)

METRIC_SPEC_PATH = "docs/specs/social-navigation-metrics.md"

__all__ = [
    "METRIC_SPEC_PATH",
    "SOCIAL_NAVIGATION_METRIC_IDS",
    "MetricContext",
    "MetricFunction",
    "MetricRegistry",
    "MetricStatus",
    "MetricValue",
    "PlaceholderMetricFunction",
    "default_metric_registry",
]

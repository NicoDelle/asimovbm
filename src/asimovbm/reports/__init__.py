"""Report builders for benchmark outputs."""

from .json_report import (
    JsonReportConfig,
    JsonReportInput,
    MetricFreezeRequiredError,
    build_behavioral_metric_block,
    build_json_report,
)

__all__ = [
    "JsonReportConfig",
    "JsonReportInput",
    "MetricFreezeRequiredError",
    "build_behavioral_metric_block",
    "build_json_report",
]

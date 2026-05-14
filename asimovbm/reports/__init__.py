"""Report builders for benchmark outputs."""

from .csv_report import (
    EPISODE_METRICS_CSV_STEM,
    MetricCsvReportError,
    append_episode_metrics_csv_row,
    build_episode_metrics_csv_row,
    episode_metrics_csv_header,
)
from .json_report import (
    JsonReportConfig,
    JsonReportInput,
    MetricFreezeRequiredError,
    build_behavioral_metric_block,
    build_json_report,
)

__all__ = [
    "EPISODE_METRICS_CSV_STEM",
    "JsonReportConfig",
    "JsonReportInput",
    "MetricCsvReportError",
    "MetricFreezeRequiredError",
    "append_episode_metrics_csv_row",
    "build_behavioral_metric_block",
    "build_episode_metrics_csv_row",
    "build_json_report",
    "episode_metrics_csv_header",
]

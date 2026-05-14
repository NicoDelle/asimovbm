"""CSV export helpers for per-episode metric reports."""

from __future__ import annotations

import csv
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from asimovbm.metrics import SOCIAL_NAVIGATION_AXIS_IDS, SOCIAL_NAVIGATION_METRIC_IDS

EPISODE_METRICS_CSV_STEM = "episode-metrics"
EPISODE_METRICS_METADATA_COLUMNS: tuple[str, ...] = (
    "run_id",
    "episode_id",
    "episode_title",
    "iteration",
    "tier_id",
    "technical_valid",
    "terminal_status",
    "canonical_backend_id",
    "execution_backend_id",
    "trace_source",
    "real_backend_verified",
)


class MetricCsvReportError(ValueError):
    """Raised when a metric report cannot be projected to CSV safely."""


def episode_metrics_csv_header() -> tuple[str, ...]:
    return (
        EPISODE_METRICS_METADATA_COLUMNS
        + SOCIAL_NAVIGATION_AXIS_IDS
        + SOCIAL_NAVIGATION_METRIC_IDS
    )


def build_episode_metrics_csv_row(
    run_id: str,
    metric_report: Mapping[str, Any],
    *,
    episode_title: str | None = None,
    tier_id: str | None = None,
    canonical_backend_id: str | None = None,
    execution_backend_id: str | None = None,
    trace_source: str | None = None,
    real_backend_verified: bool | None = None,
) -> dict[str, str]:
    behavioral = _required_mapping(
        metric_report.get("behavioral_metrics"),
        "behavioral_metrics",
    )
    row = {
        "run_id": run_id,
        "episode_id": _string(metric_report.get("episode_id")),
        "episode_title": _string(episode_title),
        "iteration": _string(metric_report.get("iteration")),
        "tier_id": _string(tier_id),
        "technical_valid": _bool_string(metric_report.get("technical_valid")),
        "terminal_status": _string(metric_report.get("terminal_status")),
        "canonical_backend_id": _string(canonical_backend_id or metric_report.get("canonical_backend_id")),
        "execution_backend_id": _string(execution_backend_id or metric_report.get("execution_backend_id")),
        "trace_source": _string(trace_source or metric_report.get("trace_source")),
        "real_backend_verified": _bool_string(
            real_backend_verified
            if real_backend_verified is not None
            else metric_report.get("real_backend_verified")
        ),
    }
    axes = _required_mapping(behavioral.get("axes"), "behavioral_metrics.axes")
    for axis_id in SOCIAL_NAVIGATION_AXIS_IDS:
        axis = _optional_mapping(axes, axis_id, f"behavioral_metrics.axes.{axis_id}")
        row[axis_id] = _score_string(axis.get("score"))
    features = _required_mapping(behavioral.get("features"), "behavioral_metrics.features")
    for metric_id in SOCIAL_NAVIGATION_METRIC_IDS:
        feature = _optional_mapping(
            features,
            metric_id,
            f"behavioral_metrics.features.{metric_id}",
        )
        row[metric_id] = _score_string(feature.get("normalized_score"))
    return row


def append_episode_metrics_csv_row(path: Path, row: Mapping[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    should_write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=episode_metrics_csv_header())
        if should_write_header:
            writer.writeheader()
        writer.writerow({column: row.get(column, "") for column in episode_metrics_csv_header()})


def _required_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    raise MetricCsvReportError(f"metric report field {label!r} must be a JSON object")


def _optional_mapping(container: Mapping[str, Any], key: str, label: str) -> Mapping[str, Any]:
    if key not in container:
        return {}
    value = container[key]
    if isinstance(value, Mapping):
        return value
    raise MetricCsvReportError(f"metric report field {label!r} must be a JSON object")


def _score_string(value: Any) -> str:
    if not isinstance(value, int | float):
        return ""
    return repr(float(value))


def _bool_string(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return _string(value)


def _string(value: Any) -> str:
    return "" if value is None else str(value)

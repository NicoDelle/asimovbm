from __future__ import annotations

import csv
from pathlib import Path

from asimovbm.reports import (
    append_episode_metrics_csv_row,
    build_episode_metrics_csv_row,
    episode_metrics_csv_header,
)


def _metric_report() -> dict:
    return {
        "episode_id": "g1_approach_user",
        "iteration": 0,
        "technical_valid": True,
        "terminal_status": "success",
        "behavioral_metrics": {
            "axes": {
                "perceived_dexterity": {"score": 0.8},
                "perceived_safety": {"score": 0.7},
            }
        },
        "metrics": {
            "task_success_rate": {"normalized_score": 1.0},
            "task_completion_time": {"normalized_score": 0.5},
        },
    }


def test_build_episode_metrics_csv_row_serializes_axes_and_metrics() -> None:
    row = build_episode_metrics_csv_row(
        "run-1",
        _metric_report(),
        episode_title="Approach user",
        tier_id="local",
    )

    assert row["run_id"] == "run-1"
    assert row["episode_id"] == "g1_approach_user"
    assert row["technical_valid"] == "true"
    assert row["perceived_dexterity"] == "0.8"
    assert row["task_success_rate"] == "1.0"
    assert row["proxemic_intrusion_dose"] == ""


def test_append_episode_metrics_csv_row_writes_header_once(tmp_path: Path) -> None:
    path = tmp_path / "episode-metrics-000.csv"
    row = build_episode_metrics_csv_row("run-1", _metric_report())

    append_episode_metrics_csv_row(path, row)
    append_episode_metrics_csv_row(path, row)

    lines = path.read_text(encoding="utf-8").splitlines()
    records = list(csv.DictReader(lines))
    assert lines[0].split(",") == list(episode_metrics_csv_header())
    assert len(records) == 2

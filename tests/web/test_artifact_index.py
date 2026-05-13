from __future__ import annotations

import json
from pathlib import Path

from asimovbm.web.artifact_index import list_runs, load_run


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_list_runs_returns_manifest_and_report_summary(tmp_path: Path) -> None:
    run_dir = tmp_path / "local-test"
    _write_json(
        run_dir / "manifest.json",
        {
            "run_id": "local-test",
            "created_at": "2026-05-13T10:00:00+00:00",
            "viewer_mode": "headless",
            "selected_episode_ids": ["g1_approach_user"],
            "records": [],
        },
    )
    _write_json(
        run_dir / "report.json",
        {
            "technical_reliability": {
                "total_episode_runs": 1,
                "technical_valid_episode_runs": 1,
            }
        },
    )

    runs = list_runs(tmp_path)

    assert runs == [
        {
            "run_id": "local-test",
            "status": "ready",
            "created_at": "2026-05-13T10:00:00+00:00",
            "viewer_mode": "headless",
            "selected_episode_ids": ["g1_approach_user"],
            "reliability": {
                "total_episode_runs": 1,
                "technical_valid_episode_runs": 1,
            },
            "errors": [],
        }
    ]


def test_load_run_resolves_record_metric_paths(tmp_path: Path) -> None:
    run_dir = tmp_path / "local-test"
    _write_json(
        run_dir / "manifest.json",
        {
            "run_id": "local-test",
            "records": [
                {
                    "episode_id": "g1_approach_user",
                    "trace_path": "g1_approach_user/iteration-000/trace.json",
                    "metrics_path": "g1_approach_user/iteration-000/metrics.json",
                }
            ],
        },
    )
    _write_json(run_dir / "report.json", {"technical_reliability": {}})
    _write_json(
        run_dir / "g1_approach_user" / "iteration-000" / "metrics.json",
        {"behavioral_metrics": {"status": "scored"}},
    )
    (run_dir / "g1_approach_user" / "iteration-000" / "trace.json").write_text(
        "{}",
        encoding="utf-8",
    )

    payload = load_run(tmp_path, "local-test")

    assert payload["status"] == "ready"
    assert payload["records"][0]["metrics"]["behavioral_metrics"]["status"] == "scored"
    assert payload["records"][0]["trace_exists"] is True


def test_list_runs_reports_incomplete_runs_without_breaking(tmp_path: Path) -> None:
    run_dir = tmp_path / "bad-run"
    _write_json(run_dir / "manifest.json", {"run_id": "bad-run", "records": []})

    runs = list_runs(tmp_path)

    assert runs[0]["status"] == "incomplete"
    assert runs[0]["errors"][0]["reason"] == "missing"

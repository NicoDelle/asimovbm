from __future__ import annotations

import json
from pathlib import Path

import pytest

from asimovbm.local_runner.unity_ingest import (
    UnityIngestConfig,
    UnityTraceIngestError,
    ingest_unity_trace_file,
)


def moving_unity_trace() -> dict:
    return {
        "schema_version": "asimovbm.unity_trace.v1",
        "scene_id": "g1_real_motion",
        "episode_id": "g1_approach_user",
        "iteration": 0,
        "tier_id": "unity_g1",
        "technical_valid": True,
        "terminal_status": "success",
        "config_checksum_sha256": "abc123",
        "config_path": "Assets/AsimovBM/MuJoCo/SceneManifest.json",
        "robot_selector": "official_g1",
        "canonical_backend_id": "g1_robojudo",
        "execution_backend_id": "unity_mujoco_trace_v1",
        "viewer_mode": "unity_batchmode",
        "metadata": {
            "start": [0.0, 0.0],
            "goal": [1.0, 0.0],
            "movement_proof": {"passed": True, "max_qpos_delta": 0.4},
        },
        "steps": [
            {
                "step_id": 0,
                "time_s": 0.1,
                "dt_s": 0.1,
                "robot_pose": [0.0, 0.0, 0.0],
                "robot_velocity": [0.0, 0.0, 0.0],
                "action": [0.0, 0.0],
                "distance_to_goal": 1.0,
                "qpos": [0.0, 0.0, 0.0],
                "qvel": [0.0, 0.0, 0.0],
                "status": "running",
            },
            {
                "step_id": 1,
                "time_s": 0.2,
                "dt_s": 0.1,
                "robot_pose": [0.5, 0.0, 0.0],
                "robot_velocity": [5.0, 0.0, 0.0],
                "action": [0.0, 0.0],
                "distance_to_goal": 0.5,
                "qpos": [0.5, 0.0, 0.0],
                "qvel": [5.0, 0.0, 0.0],
                "status": "success",
            },
        ],
    }


def write_trace(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "raw-unity-trace.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_ingests_unity_trace_and_writes_local_artifacts(tmp_path: Path) -> None:
    raw_trace = write_trace(tmp_path, moving_unity_trace())

    result = ingest_unity_trace_file(
        raw_trace,
        config=UnityIngestConfig(artifact_root=tmp_path / "artifacts", run_id="unity-smoke"),
    )

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    record = manifest["records"][0]
    trace = json.loads((result.run_dir / record["trace_path"]).read_text(encoding="utf-8"))
    metrics = json.loads((result.run_dir / record["metrics_path"]).read_text(encoding="utf-8"))
    report = json.loads(result.report_path.read_text(encoding="utf-8"))

    assert manifest["schema_version"] == "asimovbm.unity_validation.v1"
    assert manifest["run_id"] == "unity-smoke"
    assert manifest["metrics_csv_path"] == "episode-metrics-000.csv"
    assert result.metrics_csv_path.name == "episode-metrics-000.csv"
    assert record["episode_id"] == "g1_approach_user"
    assert trace["execution_backend_id"] == "unity_mujoco_trace_v1"
    assert trace["steps"][1]["robot_pose"] == [0.5, 0.0, 0.0]
    assert metrics["metrics"]["task_success_rate"]["status"] == "computed"
    assert metrics["metrics"]["min_human_robot_distance"]["status"] == "insufficient_evidence"
    assert report["technical_reliability"]["technical_valid_episode_runs"] == 1
    assert (result.run_dir / manifest["metrics_csv_path"]).exists()


def test_technical_failure_trace_produces_insufficient_evidence_metrics(tmp_path: Path) -> None:
    payload = moving_unity_trace()
    payload["technical_valid"] = False
    payload["terminal_status"] = "robot_failure"
    payload["steps"] = []
    raw_trace = write_trace(tmp_path, payload)

    result = ingest_unity_trace_file(
        raw_trace,
        config=UnityIngestConfig(artifact_root=tmp_path / "artifacts", run_id="unity-failed"),
    )

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    metrics_path = result.run_dir / manifest["records"][0]["metrics_path"]
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))

    assert manifest["records"][0]["technical_valid"] is False
    assert metrics["metrics"]["task_success_rate"]["status"] == "insufficient_evidence"
    assert "technical failure" in metrics["metrics"]["task_success_rate"]["reason"]


def test_rejects_malformed_unity_trace(tmp_path: Path) -> None:
    raw_trace = write_trace(tmp_path, {"schema_version": "asimovbm.unity_trace.v1"})

    with pytest.raises(UnityTraceIngestError, match="steps array"):
        ingest_unity_trace_file(raw_trace, config=UnityIngestConfig(artifact_root=tmp_path))

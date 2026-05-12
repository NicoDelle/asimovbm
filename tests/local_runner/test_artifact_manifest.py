from __future__ import annotations

import json
from pathlib import Path

from asimovbm.local_runner.runner import LocalRunConfig, run_local_validation
from asimovbm.local_runner.traces import LocalEpisodeTrace, LocalStepTrace


class FakeTraceBackend:
    backend_id = "fake_trace_backend"

    def run_episode(self, spec, *, iteration: int, viewer_enabled: bool):
        return LocalEpisodeTrace(
            episode_id=spec.id,
            iteration=iteration,
            tier_id="g1_slam_canonical",
            technical_valid=True,
            terminal_status="success",
            steps=tuple(
                LocalStepTrace(
                    step_id=index,
                    time_s=float(index + 1),
                    dt_s=1.0,
                    robot_pose=(float(index) * 0.3, 0.0, 0.0),
                    robot_velocity=(0.3, 0.0, 0.0),
                    action=(0.3, 0.0),
                    distance_to_goal=max(0.0, 1.0 - index * 0.3),
                )
                for index in range(5)
            ),
            config_checksum_sha256=spec.checksum_sha256,
            config_path=spec.path.as_posix(),
            robot_selector=spec.robot_selector,
            canonical_backend_id=spec.canonical_backend_id,
            execution_backend_id=self.backend_id,
            viewer_mode="visible" if viewer_enabled else "headless",
            measurement_backend_id="reference",
            measurement_proof_level="reference",
        )


class LeakyObservationBackend:
    backend_id = "leaky_trace_backend"

    def run_episode(self, spec, *, iteration: int, viewer_enabled: bool):
        return LocalEpisodeTrace(
            episode_id=spec.id,
            iteration=iteration,
            tier_id="g1_slam_canonical",
            technical_valid=True,
            terminal_status="success",
            steps=(
                LocalStepTrace(
                    step_id=0,
                    time_s=1.0,
                    dt_s=1.0,
                    robot_pose=(0.0, 0.0, 0.0),
                    robot_velocity=(0.0, 0.0, 0.0),
                    action=(0.0, 0.0),
                    distance_to_goal=1.0,
                    public_observation={"hidden_target_role": "target"},
                ),
            ),
            config_checksum_sha256=spec.checksum_sha256,
            config_path=spec.path.as_posix(),
            robot_selector=spec.robot_selector,
            canonical_backend_id=spec.canonical_backend_id,
            execution_backend_id=self.backend_id,
            viewer_mode="headless",
            measurement_backend_id="reference",
            measurement_proof_level="reference",
        )


def test_local_run_writes_manifest_trace_metrics_and_report(tmp_path: Path) -> None:
    result = run_local_validation(
        LocalRunConfig(
            artifact_root=tmp_path,
            run_id="test-run",
            iterations=1,
            episode_ids=("g1_approach_user",),
            backend=FakeTraceBackend(),
        )
    )

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

    assert manifest["run_id"] == "test-run"
    assert manifest["viewer_mode"] == "visible"
    assert manifest["selected_episode_ids"] == ["g1_approach_user"]
    assert manifest["measurement_backend"] == "reference"
    assert manifest["records"][0]["trace_path"] == "g1_approach_user/iteration-000/trace.json"
    assert manifest["records"][0]["measurement_proof_level"] == "reference"
    assert manifest["records"][0]["validation_status"] == "valid"
    assert (result.run_dir / manifest["records"][0]["trace_path"]).exists()
    assert (result.run_dir / manifest["records"][0]["metrics_path"]).exists()
    assert result.report_path.exists()


def test_local_run_rejects_hidden_fields_in_public_observation(tmp_path: Path) -> None:
    result = run_local_validation(
        LocalRunConfig(
            artifact_root=tmp_path,
            run_id="leaky-run",
            iterations=1,
            episode_ids=("g1_approach_user",),
            backend=LeakyObservationBackend(),
            visible=False,
        )
    )

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    trace_path = result.run_dir / manifest["records"][0]["trace_path"]
    metrics_path = result.run_dir / manifest["records"][0]["metrics_path"]
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))

    assert manifest["records"][0]["technical_valid"] is False
    assert manifest["records"][0]["validation_status"] == "invalid"
    assert trace["validation_summary"]["status"] == "invalid"
    assert metrics["technical_valid"] is False


def test_mujoco_measurement_selector_reports_technical_failure_without_assets(tmp_path: Path) -> None:
    result = run_local_validation(
        LocalRunConfig(
            artifact_root=tmp_path,
            run_id="mujoco-unavailable",
            iterations=1,
            episode_ids=("g1_approach_user",),
            visible=False,
            measurement_backend="mujoco",
        )
    )

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    metrics_path = result.run_dir / manifest["records"][0]["metrics_path"]
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))

    assert manifest["measurement_backend"] == "mujoco"
    assert manifest["records"][0]["technical_valid"] is False
    assert manifest["records"][0]["measurement_proof_level"] == "unavailable"
    assert "not implemented" in manifest["records"][0]["terminal_status"]
    assert metrics["technical_valid"] is False

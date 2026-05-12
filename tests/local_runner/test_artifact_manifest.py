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
    assert manifest["records"][0]["trace_path"] == "g1_approach_user/iteration-000/trace.json"
    assert (result.run_dir / manifest["records"][0]["trace_path"]).exists()
    assert (result.run_dir / manifest["records"][0]["metrics_path"]).exists()
    assert result.report_path.exists()

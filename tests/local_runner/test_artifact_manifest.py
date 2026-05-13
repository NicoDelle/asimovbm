from __future__ import annotations

import json
from pathlib import Path

from asimovbm.local_runner.runner import LocalRunConfig, run_local_validation
from asimovbm.local_runner.traces import LocalEpisodeTrace, LocalStepTrace


class FakeTraceBackend:
    backend_id = "fake_trace_backend"

    def __init__(self) -> None:
        self.calls = []

    def run_episode(self, spec, *, iteration: int, viewer_enabled: bool, viewer_speed: float):
        self.calls.append(
            {
                "episode_id": spec.id,
                "iteration": iteration,
                "viewer_enabled": viewer_enabled,
                "viewer_speed": viewer_speed,
            }
        )
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
                    static_entities=(
                        {"id": "target_user", "type": "target", "pose": (1.2, 0.0, 0.0)},
                    ),
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
    backend = FakeTraceBackend()
    result = run_local_validation(
        LocalRunConfig(
            artifact_root=tmp_path,
            run_id="test-run",
            iterations=1,
            robot_id="g1",
            episode_ids=("g1_approach_user",),
            backend=backend,
        )
    )

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

    assert manifest["run_id"] == "test-run"
    assert manifest["robot_id"] == "g1"
    assert manifest["policy_id"] == "g1_robojudo_asap"
    assert manifest["viewer_mode"] == "visible"
    assert manifest["selected_episode_ids"] == ["g1_approach_user"]
    assert manifest["records"][0]["trace_path"] == "g1_approach_user/iteration-000/trace.json"
    assert manifest["metrics_csv_path"] == "episode-metrics-000.csv"
    assert result.metrics_csv_path.name == "episode-metrics-000.csv"
    assert (result.run_dir / manifest["records"][0]["trace_path"]).exists()
    assert (result.run_dir / manifest["records"][0]["metrics_path"]).exists()
    assert (result.run_dir / manifest["metrics_csv_path"]).exists()
    trace = json.loads((result.run_dir / manifest["records"][0]["trace_path"]).read_text(encoding="utf-8"))
    assert trace["metadata"]["robot_id"] == "g1"
    assert trace["metadata"]["policy_id"] == "g1_robojudo_asap"
    assert result.report_path.exists()
    report = json.loads(result.report_path.read_text(encoding="utf-8"))
    behavioral = report["behavioral_metrics"]
    assert behavioral["status"] == "insufficient_evidence"
    assert behavioral["aggregation_scope"] == "suite"
    assert behavioral["scoring_model"]["kind"] == "equal_weight_episode_axis_mean"
    assert behavioral["scoring_model"]["episode_axis_model"] == "manual_v1_evidence_weights"
    assert behavioral["global_score"]["status"] == "insufficient_evidence"
    assert behavioral["global_score"]["score"] is None
    assert behavioral["features"] == {}
    assert behavioral["sub_indicators"] == []
    assert behavioral["axes"]["perceived_dexterity"]["status"] == "computed"
    assert behavioral["axes"]["perceived_dexterity"]["confidence"] == "partial"
    assert behavioral["axes"]["perceived_dexterity"]["source_episode_evidence_gaps"]
    assert behavioral["axes"]["perceived_dexterity"]["contributing_episode_runs"] == [
        {"episode_id": "g1_approach_user", "iteration": 0}
    ]
    assert behavioral["episode_blocks"][0]["episode_id"] == "g1_approach_user"
    metrics_csv = (result.run_dir / manifest["metrics_csv_path"]).read_text(encoding="utf-8")
    assert "perceived_dexterity" in metrics_csv
    assert "g1_approach_user" in metrics_csv
    assert backend.calls == [
        {
            "episode_id": "g1_approach_user",
            "iteration": 0,
            "viewer_enabled": True,
            "viewer_speed": 4.0,
        }
    ]


def test_default_single_iteration_requests_visible_viewer_for_selected_robot_episodes(tmp_path: Path) -> None:
    backend = FakeTraceBackend()

    run_local_validation(
        LocalRunConfig(
            artifact_root=tmp_path,
            run_id="visible-g1-episodes",
            iterations=1,
            robot_id="g1",
            backend=backend,
        )
    )

    assert len(backend.calls) == 3
    assert all(call["viewer_enabled"] is True for call in backend.calls)
    assert [call["episode_id"] for call in backend.calls] == [
        "g1_approach_user",
        "g1_lateral_open",
        "g1_lateral_static_dynamic_obstacles",
    ]

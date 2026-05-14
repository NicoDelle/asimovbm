from __future__ import annotations

import json
from pathlib import Path

from asimovbm.local_runner import survey_export
from asimovbm.local_runner.runner import LocalRunConfig, run_local_validation
from asimovbm.local_runner.traces import LocalEpisodeTrace, LocalStepTrace


class FakeTraceBackend:
    backend_id = "fake_trace_backend"

    def __init__(self) -> None:
        self.calls = []

    def run_episode(
        self,
        spec,
        *,
        iteration: int,
        viewer_enabled: bool,
        viewer_speed: float,
        camera_view: str,
    ):
        self.calls.append(
            {
                "episode_id": spec.id,
                "iteration": iteration,
                "viewer_enabled": viewer_enabled,
                "viewer_speed": viewer_speed,
                "camera_view": camera_view,
                "controller_start_delay_s": spec.config.controller.start_delay_s,
                "start": (spec.config.start.x, spec.config.start.y, spec.config.start.yaw),
                "goal": spec.config.goal,
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
            episode_ids=("g1_point_to_point_open",),
            backend=backend,
        )
    )

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

    assert manifest["run_id"] == "test-run"
    assert manifest["robot_id"] == "g1"
    assert manifest["policy_id"] == "g1_robojudo_asap"
    assert manifest["viewer_mode"] == "visible"
    assert manifest["selected_episode_ids"] == ["g1_point_to_point_open"]
    assert manifest["records"][0]["trace_path"] == "g1_point_to_point_open/iteration-000/trace.json"
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
        {"episode_id": "g1_point_to_point_open", "iteration": 0}
    ]
    assert behavioral["episode_blocks"][0]["episode_id"] == "g1_point_to_point_open"
    metrics_csv = (result.run_dir / manifest["metrics_csv_path"]).read_text(encoding="utf-8")
    assert "perceived_dexterity" in metrics_csv
    assert "g1_point_to_point_open" in metrics_csv
    assert backend.calls == [
        {
            "episode_id": "g1_point_to_point_open",
            "iteration": 0,
            "viewer_enabled": True,
            "viewer_speed": 4.0,
            "camera_view": "config",
            "controller_start_delay_s": 1.0,
            "start": (-2.5, 1.6, 0.35),
            "goal": (2.5, 1.6),
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
        "g1_point_to_point_open",
        "g1_point_to_point_static_obstacles",
        "g1_point_to_point_dynamic_npcs",
    ]
    assert backend.calls[-1]["controller_start_delay_s"] == 0.0
    assert backend.calls[-1]["start"] == (-3.65, -1.6, 0.35)
    assert backend.calls[-1]["goal"] == (5.0, -1.6)


def test_policy_b_dynamic_npc_episode_uses_survey_start_timing(tmp_path: Path) -> None:
    backend = FakeTraceBackend()

    run_local_validation(
        LocalRunConfig(
            artifact_root=tmp_path,
            run_id="policy-b-dynamic",
            iterations=1,
            robot_id="g1",
            policy_id="g1_robojudo_asap",
            episode_ids=("g1_point_to_point_dynamic_npcs",),
            backend=backend,
        )
    )

    assert backend.calls == [
        {
            "episode_id": "g1_point_to_point_dynamic_npcs",
            "iteration": 0,
            "viewer_enabled": True,
            "viewer_speed": 4.0,
            "camera_view": "config",
            "controller_start_delay_s": 0.0,
            "start": (-3.65, -1.6, 0.35),
            "goal": (5.0, -1.6),
        }
    ]


def test_start_x_offset_override_applies_to_selected_episode(tmp_path: Path) -> None:
    backend = FakeTraceBackend()

    run_local_validation(
        LocalRunConfig(
            artifact_root=tmp_path,
            run_id="explicit-start-x-offset",
            iterations=1,
            robot_id="g1",
            policy_id="g1_robojudo_asap",
            episode_ids=("g1_point_to_point_dynamic_npcs",),
            start_x_offset_m=0.2,
            backend=backend,
        )
    )

    assert backend.calls[0]["start"] == (-3.8, -1.6, 0.35)
    assert backend.calls[0]["goal"] == (5.0, -1.6)


def test_route_y_offset_override_still_applies_to_selected_episode(tmp_path: Path) -> None:
    backend = FakeTraceBackend()

    run_local_validation(
        LocalRunConfig(
            artifact_root=tmp_path,
            run_id="explicit-route-offset",
            iterations=1,
            robot_id="g1",
            policy_id="g1_robojudo_asap",
            episode_ids=("g1_point_to_point_dynamic_npcs",),
            start_x_offset_m=0.0,
            route_y_offset_m=-0.2,
            backend=backend,
        )
    )

    assert backend.calls[0]["start"] == (-4.0, -1.8, 0.35)
    assert backend.calls[0]["goal"] == (5.0, -1.8)


def test_start_delay_override_applies_to_selected_episode(tmp_path: Path) -> None:
    backend = FakeTraceBackend()

    run_local_validation(
        LocalRunConfig(
            artifact_root=tmp_path,
            run_id="explicit-start-delay",
            iterations=1,
            robot_id="g1",
            policy_id="g1_robojudo_unitree",
            episode_ids=("g1_point_to_point_open",),
            start_delay_s=0.25,
            backend=backend,
        )
    )

    assert backend.calls[0]["controller_start_delay_s"] == 0.25
    assert backend.calls[0]["start"] == (-2.5, 1.6, 0.35)


def test_local_run_can_export_survey_videos_and_sidecars(tmp_path: Path, monkeypatch) -> None:
    backend = FakeTraceBackend()
    rendered = []

    def fake_render(record, spec, *, view: str, output_path: Path, config) -> None:
        rendered.append((record.trace.episode_id, spec.robot_selector, view, config.fps))
        output_path.write_bytes(b"fake-mujoco-video")

    monkeypatch.setattr(survey_export, "_render_mujoco_video", fake_render)
    result = run_local_validation(
        LocalRunConfig(
            artifact_root=tmp_path / "local",
            run_id="survey-run",
            iterations=1,
            robot_id="g1",
            policy_id="g1_robojudo_unitree",
            episode_ids=("g1_point_to_point_open",),
            backend=backend,
            survey_export=True,
            survey_root=tmp_path / "survey",
            survey_policy_id="policy_a",
            survey_video_fps=4,
        )
    )

    assert result.survey_export is not None
    assert backend.calls[0]["viewer_enabled"] is False
    assert rendered == [
        ("g1_point_to_point_open", "official_g1", "arrival", 4),
        ("g1_point_to_point_open", "official_g1", "bystander", 4),
    ]
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["survey_export"]["summary_json_path"].endswith("metrics-summary-survey-run.json")
    assert len(result.survey_export.videos) == 2

    for view in ("arrival", "bystander"):
        video_path = (
            tmp_path
            / "survey"
            / "videos"
            / "policy_a"
            / view
            / "g1_point_to_point_open.mp4"
        )
        json_path = (
            tmp_path
            / "survey"
            / "json"
            / "policy_a"
            / view
            / "g1_point_to_point_open.json"
        )
        assert video_path.exists()
        assert video_path.stat().st_size > 0
        sidecar = json.loads(json_path.read_text(encoding="utf-8"))
        assert sidecar["episode_id"] == "g1_point_to_point_open"
        assert sidecar["source_episode_id"] == "g1_point_to_point_open"
        assert sidecar["policy_id"] == "policy_a"
        assert sidecar["camera_view"] == view
        assert sidecar["render_backend"]["kind"] == "mujoco_offscreen"
        assert sidecar["render_backend"]["robot_selector"] == "official_g1"
        assert sidecar["render_backend"]["width"] == 1280
        assert sidecar["render_backend"]["height"] == 720
        assert sidecar["render_backend"]["video_codec"] == "h264"
        assert sidecar["render_backend"]["max_duration_s"] == 15.0
        assert set(sidecar["metric_report"]["behavioral_metrics"]["axes"]) >= {
            "perceived_dexterity",
            "perceived_safety",
            "perceived_social_awareness",
            "impression",
        }

    summary = json.loads((tmp_path / "survey" / "metrics-summary-survey-run.json").read_text(encoding="utf-8"))
    assert summary["video_count"] == 2

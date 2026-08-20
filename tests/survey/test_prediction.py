from __future__ import annotations

import json
from pathlib import Path

from asimovbm.survey.prediction import load_video_prediction
from asimovbm.survey.video_manifest import PredictionSource, SurveyVideo


def _video(source: PredictionSource) -> SurveyVideo:
    return SurveyVideo(
        video_id="video-1",
        path="video-1.mp4",
        policy_id="policy_a",
        viewpoint="first_person",
        robot_id="g1",
        episode_id="g1_point_to_point_open",
        group_ids=("policy_a_fp",),
        prediction_source=source,
    )


def _metric_report() -> dict:
    return {
        "episode_id": "g1_point_to_point_open",
        "iteration": 0,
        "technical_valid": True,
        "terminal_status": "success",
        "behavioral_metrics": {
            "axes": {
                "perceived_dexterity": {"score": 0.8},
                "perceived_safety": {"score": 0.7},
                "perceived_social_awareness": {"score": 0.6},
                "impression": {"score": 0.5},
            }
        },
        "metrics": {"task_success_rate": {"normalized_score": 1.0}},
    }


def test_loads_prediction_from_metrics_json(tmp_path: Path) -> None:
    (tmp_path / "metrics.json").write_text(json.dumps(_metric_report()), encoding="utf-8")
    prediction = load_video_prediction(
        _video(PredictionSource(kind="metrics_json", path="metrics.json")),
        artifact_root=tmp_path,
    )

    assert prediction["status"] == "computed"
    assert prediction["axes"]["perceived_dexterity"]["score"] == 80
    assert prediction["features"]["task_success_rate"]["score"] == 100


def test_loads_prediction_from_named_source_root(tmp_path: Path) -> None:
    json_root = tmp_path / "survey-json"
    json_root.mkdir()
    (json_root / "sidecar.json").write_text(json.dumps(_metric_report()), encoding="utf-8")

    prediction = load_video_prediction(
        _video(PredictionSource(kind="simulation_json", path="sidecar.json", root="survey_json_root")),
        artifact_root=tmp_path / "runs",
        source_roots={"survey_json_root": json_root},
    )

    assert prediction["status"] == "computed"
    assert prediction["axes"]["perceived_safety"]["score"] == 70


def test_loads_prediction_from_episode_metrics_csv(tmp_path: Path) -> None:
    (tmp_path / "episode-metrics-000.csv").write_text(
        "\n".join(
            [
                "run_id,episode_id,episode_title,iteration,tier_id,technical_valid,terminal_status,"
                "perceived_dexterity,perceived_safety,perceived_social_awareness,impression,"
                "task_success_rate,task_completion_time,comfort_aware_path_efficiency,hesitation,"
                "min_human_robot_distance,proxemic_intrusion_dose,speed_near_humans_p95,"
                "gesture_response_success,acknowledgement_clarity,human_aware_approach,bystander_ack,"
                "sparc,heading_jerk,stability,legibility,behavioral_naturalness",
                "run-1,g1_point_to_point_open,Approach,0,local,true,success,0.8,0.7,0.6,0.5,1.0,,,,,,,,,,,,,,,",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    prediction = load_video_prediction(
        _video(
            PredictionSource(
                kind="episode_metrics_csv",
                path="episode-metrics-000.csv",
                run_id="run-1",
                iteration=0,
            )
        ),
        artifact_root=tmp_path,
    )

    assert prediction["status"] == "computed"
    assert prediction["axes"]["impression"]["score"] == 50


def test_loads_prediction_from_local_trace_json(tmp_path: Path) -> None:
    trace = {
        "episode_id": "g1_point_to_point_open",
        "iteration": 0,
        "tier_id": "local",
        "technical_valid": True,
        "terminal_status": "success",
        "config_checksum_sha256": "abc",
        "config_path": "episode.json",
        "robot_selector": "official_g1",
        "canonical_backend_id": "g1_robojudo",
        "execution_backend_id": "fake",
        "viewer_mode": "headless",
        "metadata": {"start": [0.0, 0.0], "goal": [1.0, 0.0]},
        "steps": [
            {
                "step_id": 0,
                "time_s": 0.0,
                "dt_s": 0.1,
                "robot_pose": [0.0, 0.0, 0.0],
                "robot_velocity": [0.0, 0.0, 0.0],
                "action": [0.0, 0.0],
                "distance_to_goal": 1.0,
                "static_entities": [{"id": "target", "type": "target", "pose": [1.0, 0.0, 0.0]}],
                "status": "running",
            },
            {
                "step_id": 1,
                "time_s": 1.0,
                "dt_s": 0.1,
                "robot_pose": [1.0, 0.0, 0.0],
                "robot_velocity": [1.0, 0.0, 0.0],
                "action": [1.0, 0.0],
                "distance_to_goal": 0.0,
                "static_entities": [{"id": "target", "type": "target", "pose": [1.0, 0.0, 0.0]}],
                "status": "success",
            },
        ],
    }
    (tmp_path / "trace.json").write_text(json.dumps(trace), encoding="utf-8")

    prediction = load_video_prediction(
        _video(PredictionSource(kind="simulation_json", path="trace.json")),
        artifact_root=tmp_path,
    )

    assert prediction["status"] == "computed"
    assert prediction["axes"]["perceived_dexterity"]["score"] is not None


def test_loads_prediction_from_nested_sidecar_replay(tmp_path: Path) -> None:
    sidecar = {
        "episode_id": "g1_point_to_point_open",
        "robot_id": "g1",
        "policy_id": "policy_a",
        "camera_view": "arrival",
        "trace": _local_trace_payload(),
    }
    (tmp_path / "sidecar.json").write_text(json.dumps(sidecar), encoding="utf-8")

    prediction = load_video_prediction(
        _video(PredictionSource(kind="simulation_json", path="sidecar.json")),
        artifact_root=tmp_path,
    )

    assert prediction["status"] == "computed"
    assert prediction["axes"]["perceived_dexterity"]["score"] is not None


def _local_trace_payload() -> dict:
    return {
        "episode_id": "g1_point_to_point_open",
        "iteration": 0,
        "tier_id": "local",
        "technical_valid": True,
        "terminal_status": "success",
        "config_checksum_sha256": "abc",
        "config_path": "episode.json",
        "robot_selector": "official_g1",
        "canonical_backend_id": "g1_robojudo",
        "execution_backend_id": "fake",
        "viewer_mode": "headless",
        "metadata": {"start": [0.0, 0.0], "goal": [1.0, 0.0]},
        "steps": [
            {
                "step_id": 0,
                "time_s": 0.0,
                "dt_s": 0.1,
                "robot_pose": [0.0, 0.0, 0.0],
                "robot_velocity": [0.0, 0.0, 0.0],
                "action": [0.0, 0.0],
                "distance_to_goal": 1.0,
                "static_entities": [{"id": "target", "type": "target", "pose": [1.0, 0.0, 0.0]}],
                "status": "running",
            },
            {
                "step_id": 1,
                "time_s": 1.0,
                "dt_s": 0.1,
                "robot_pose": [1.0, 0.0, 0.0],
                "robot_velocity": [1.0, 0.0, 0.0],
                "action": [1.0, 0.0],
                "distance_to_goal": 0.0,
                "static_entities": [{"id": "target", "type": "target", "pose": [1.0, 0.0, 0.0]}],
                "status": "success",
            },
        ],
    }

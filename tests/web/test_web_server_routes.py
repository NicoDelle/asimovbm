from __future__ import annotations

import json
from pathlib import Path

from asimovbm.web.server import WebApp, WebConfig, build_parser


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _manifest(path: Path) -> None:
    _write_json(
        path,
        {
            "study_id": "pilot",
            "videos": [
                {
                    "video_id": "video-1",
                    "path": "video-1.mp4",
                    "policy_id": "policy_a",
                    "viewpoint": "first_person",
                    "robot_id": "g1",
                    "episode_id": "g1_approach_user",
                    "group_ids": ["policy_a_fp"],
                    "episode_order": 1,
                }
            ],
        },
    )


def _two_group_manifest(path: Path) -> None:
    _write_json(
        path,
        {
            "study_id": "pilot",
            "videos": [
                {
                    "video_id": "a-video",
                    "path": "a-video.mp4",
                    "policy_id": "policy_a",
                    "viewpoint": "first_person",
                    "robot_id": "g1",
                    "episode_id": "g1_approach_user",
                    "group_ids": ["policy_a_fp"],
                    "episode_order": 1,
                },
                {
                    "video_id": "b-video",
                    "path": "b-video.mp4",
                    "policy_id": "policy_b",
                    "viewpoint": "first_person",
                    "robot_id": "g1",
                    "episode_id": "g1_approach_user",
                    "group_ids": ["policy_b_fp"],
                    "episode_order": 1,
                },
            ],
        },
    )


def test_dashboard_route_serves_html(tmp_path: Path) -> None:
    app = WebApp(WebConfig(artifact_root=tmp_path))

    response = app.handle_request("GET", "/")

    assert response.status == 200
    assert response.content_type == "text/html"
    assert b"Asimov Benchmark" in response.body


def test_runs_api_returns_artifact_runs(tmp_path: Path) -> None:
    run_dir = tmp_path / "local-test"
    _write_json(run_dir / "manifest.json", {"run_id": "local-test", "records": []})
    _write_json(run_dir / "report.json", {"technical_reliability": {}})
    app = WebApp(WebConfig(artifact_root=tmp_path))

    response = app.handle_request("GET", "/api/runs")

    assert json.loads(response.body)["runs"][0]["run_id"] == "local-test"


def test_survey_design_endpoint_includes_q5_when_enabled(tmp_path: Path) -> None:
    app = WebApp(WebConfig(artifact_root=tmp_path, include_q5=True))

    response = app.handle_request("GET", "/api/survey/design")
    payload = json.loads(response.body)

    assert "appropriate_behavior" in {question["id"] for question in payload["questions"]}


def test_survey_video_and_response_flow_writes_artifacts(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    video_root = tmp_path / "videos"
    video_root.mkdir()
    (video_root / "video-1.mp4").write_bytes(b"fake")
    _manifest(manifest_path)
    app = WebApp(
        WebConfig(
            artifact_root=tmp_path / "runs",
            survey_root=tmp_path / "survey",
            video_root=video_root,
            video_manifest_path=manifest_path,
        )
    )

    videos_response = app.handle_request("GET", "/api/survey/videos?group=policy_a_fp")
    participant_response = app.handle_request(
        "POST",
        "/api/survey/participants",
        json.dumps({"participant_id": "p1", "group_id": "policy_a_fp"}).encode(),
    )
    response_response = app.handle_request(
        "POST",
        "/api/survey/responses",
        json.dumps(
            {
                "participant_id": "p1",
                "group_id": "policy_a_fp",
                "video_id": "video-1",
                "answers": {
                    "competent_control": 7,
                    "safe_behavior": 7,
                    "surrounding_awareness": 7,
                    "positive_impression": 7,
                },
            }
        ).encode(),
    )

    assert json.loads(videos_response.body)["videos"][0]["video_id"] == "video-1"
    assert participant_response.status == 201
    assert response_response.status == 201
    assert (tmp_path / "survey" / "pilot" / "responses.jsonl").exists()


def test_unknown_survey_group_returns_structured_error(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    video_root = tmp_path / "videos"
    video_root.mkdir()
    _manifest(manifest_path)
    app = WebApp(
        WebConfig(
            artifact_root=tmp_path / "runs",
            survey_root=tmp_path / "survey",
            video_root=video_root,
            video_manifest_path=manifest_path,
        )
    )

    response = app.handle_request("GET", "/api/survey/videos?group=missing")

    assert response.status == 400
    assert "unknown study cell" in json.loads(response.body)["error"]


def test_participant_csv_endpoint_exports_content(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    video_root = tmp_path / "videos"
    video_root.mkdir()
    _manifest(manifest_path)
    app = WebApp(
        WebConfig(
            artifact_root=tmp_path / "runs",
            survey_root=tmp_path / "survey",
            video_root=video_root,
            video_manifest_path=manifest_path,
        )
    )
    app.handle_request(
        "POST",
        "/api/survey/participants",
        json.dumps({"participant_id": "p1", "group_id": "policy_a_fp"}).encode(),
    )

    response = app.handle_request("GET", "/api/survey/participants.csv")

    assert response.content_type.startswith("text/csv")
    assert b"participant_id,group_id" in response.body
    assert (tmp_path / "survey" / "pilot" / "participants.csv").exists()


def test_anonymous_participant_start_assigns_least_completed_group(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    video_root = tmp_path / "videos"
    video_root.mkdir()
    (video_root / "a-video.mp4").write_bytes(b"fake")
    (video_root / "b-video.mp4").write_bytes(b"fake")
    _two_group_manifest(manifest_path)
    app = WebApp(
        WebConfig(
            artifact_root=tmp_path / "runs",
            survey_root=tmp_path / "survey",
            video_root=video_root,
            video_manifest_path=manifest_path,
        )
    )
    first_response = app.handle_request(
        "POST",
        "/api/survey/participants",
        json.dumps({}).encode(),
    )
    first = json.loads(first_response.body)
    app.handle_request(
        "POST",
        "/api/survey/responses",
        json.dumps(
            {
                "participant_id": first["participant"]["participant_id"],
                "group_id": "policy_a_fp",
                "video_id": "a-video",
                "video_completed": True,
                "answers": {
                    "competent_control": 7,
                    "safe_behavior": 7,
                    "surrounding_awareness": 7,
                    "positive_impression": 7,
                },
            }
        ).encode(),
    )

    second_response = app.handle_request(
        "POST",
        "/api/survey/participants",
        json.dumps({}).encode(),
    )
    second = json.loads(second_response.body)

    assert first["participant"]["participant_id"].startswith("p_")
    assert first["participant"]["group_id"] == "policy_a_fp"
    assert first["videos"][0]["video_id"] == "a-video"
    assert second["participant"]["group_id"] == "policy_b_fp"
    assert second["videos"][0]["video_id"] == "b-video"


def test_anonymous_participant_start_rejects_full_quota(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    video_root = tmp_path / "videos"
    video_root.mkdir()
    (video_root / "video-1.mp4").write_bytes(b"fake")
    _manifest(manifest_path)
    app = WebApp(
        WebConfig(
            artifact_root=tmp_path / "runs",
            survey_root=tmp_path / "survey",
            video_root=video_root,
            video_manifest_path=manifest_path,
            survey_quota_per_group=1,
        )
    )
    first_response = app.handle_request(
        "POST",
        "/api/survey/participants",
        json.dumps({}).encode(),
    )
    participant = json.loads(first_response.body)["participant"]
    app.handle_request(
        "POST",
        "/api/survey/responses",
        json.dumps(
            {
                "participant_id": participant["participant_id"],
                "group_id": "policy_a_fp",
                "video_id": "video-1",
                "video_completed": True,
                "answers": {
                    "competent_control": 7,
                    "safe_behavior": 7,
                    "surrounding_awareness": 7,
                    "positive_impression": 7,
                },
            }
        ).encode(),
    )

    second_response = app.handle_request(
        "POST",
        "/api/survey/participants",
        json.dumps({}).encode(),
    )

    assert second_response.status == 400
    assert "quota is full" in json.loads(second_response.body)["error"]


def test_prediction_and_comparison_routes_join_manifest_metrics_and_survey(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    video_root = tmp_path / "videos"
    artifact_root = tmp_path / "runs"
    video_root.mkdir()
    artifact_root.mkdir()
    (video_root / "video-1.mp4").write_bytes(b"fake")
    _write_json(
        artifact_root / "run-1" / "g1_approach_user" / "iteration-000" / "metrics.json",
        {
            "episode_id": "g1_approach_user",
            "iteration": 0,
            "technical_valid": True,
            "terminal_status": "success",
            "behavioral_metrics": {
                "axes": {
                    "perceived_dexterity": {"score": 0.8},
                    "perceived_safety": {"score": 0.8},
                    "perceived_social_awareness": {"score": 0.8},
                    "impression": {"score": 0.8},
                }
            },
            "metrics": {},
        },
    )
    _write_json(
        manifest_path,
        {
            "study_id": "pilot",
            "videos": [
                {
                    "video_id": "video-1",
                    "path": "video-1.mp4",
                    "policy_id": "policy_a",
                    "viewpoint": "first_person",
                    "robot_id": "g1",
                    "episode_id": "g1_approach_user",
                    "group_ids": ["policy_a_fp"],
                    "episode_order": 1,
                    "prediction_source": {
                        "kind": "metrics_json",
                        "path": "run-1/g1_approach_user/iteration-000/metrics.json",
                    },
                }
            ],
        },
    )
    app = WebApp(
        WebConfig(
            artifact_root=artifact_root,
            survey_root=tmp_path / "survey",
            video_root=video_root,
            video_manifest_path=manifest_path,
        )
    )
    app.handle_request(
        "POST",
        "/api/survey/participants",
        json.dumps({"participant_id": "p1", "group_id": "policy_a_fp"}).encode(),
    )
    app.handle_request(
        "POST",
        "/api/survey/responses",
        json.dumps(
            {
                "participant_id": "p1",
                "group_id": "policy_a_fp",
                "video_id": "video-1",
                "answers": {
                    "competent_control": 7,
                    "safe_behavior": 7,
                    "surrounding_awareness": 7,
                    "positive_impression": 7,
                },
            }
        ).encode(),
    )

    predictions_response = app.handle_request("GET", "/api/survey/predictions")
    comparison_response = app.handle_request("GET", "/api/survey/comparison")

    predictions = json.loads(predictions_response.body)["predictions"]
    comparison = json.loads(comparison_response.body)["comparison"]
    assert predictions["video-1"]["axes"]["perceived_dexterity"]["score"] == 80
    assert comparison["videos"]["video-1"]["status"] == "compared"
    assert comparison["videos"]["video-1"]["survey_global"] == 100


def test_server_discovers_sim_output_video_and_json_without_manifest(tmp_path: Path) -> None:
    video_root = tmp_path / "survey" / "videos"
    json_root = tmp_path / "survey" / "json"
    video_path = video_root / "policy_a" / "arrival" / "g1_point_to_point_open.mp4"
    json_path = json_root / "policy_a" / "arrival" / "g1_point_to_point_open.json"
    video_path.parent.mkdir(parents=True)
    json_path.parent.mkdir(parents=True)
    video_path.write_bytes(b"fake")
    _write_json(
        json_path,
        {
            "episode_id": "g1_point_to_point_open",
            "robot_id": "g1",
            "policy_id": "policy_a",
            "camera_view": "arrival",
            "metric_report": {
                "behavioral_metrics": {
                    "axes": {
                        "perceived_dexterity": {"score": 0.9},
                        "perceived_safety": {"score": 0.8},
                        "perceived_social_awareness": {"score": 0.7},
                        "impression": {"score": 0.6},
                    }
                },
                "metrics": {},
            },
        },
    )
    app = WebApp(
        WebConfig(
            artifact_root=tmp_path / "runs",
            survey_root=tmp_path / "survey",
            video_root=video_root,
            survey_json_root=json_root,
        )
    )

    videos_response = app.handle_request("GET", "/api/survey/videos?group=policy_a_fp")
    predictions_response = app.handle_request("GET", "/api/survey/predictions")

    videos = json.loads(videos_response.body)["videos"]
    predictions = json.loads(predictions_response.body)["predictions"]
    assert videos[0]["path"] == "policy_a/arrival/g1_point_to_point_open.mp4"
    assert videos[0]["prediction_source"]["root"] == "survey_json_root"
    assert predictions[videos[0]["video_id"]]["axes"]["perceived_dexterity"]["score"] == 90


def test_parser_accepts_web_roots_and_port() -> None:
    args = build_parser().parse_args(
        [
            "--artifact-root",
            "runs",
            "--survey-root",
            "survey",
            "--video-root",
            "videos",
            "--survey-json-root",
            "survey-json",
            "--survey-quota-per-group",
            "12",
            "--port",
            "9999",
        ]
    )

    assert args.artifact_root == Path("runs")
    assert args.survey_json_root == Path("survey-json")
    assert args.survey_quota_per_group == 12
    assert args.port == 9999

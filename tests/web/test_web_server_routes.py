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


def test_parser_accepts_web_roots_and_port() -> None:
    args = build_parser().parse_args(
        [
            "--artifact-root",
            "runs",
            "--survey-root",
            "survey",
            "--video-root",
            "videos",
            "--port",
            "9999",
        ]
    )

    assert args.artifact_root == Path("runs")
    assert args.port == 9999

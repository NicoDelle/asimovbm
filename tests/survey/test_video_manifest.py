from __future__ import annotations

from pathlib import Path

import pytest

from asimovbm.survey.video_manifest import (
    VideoManifestError,
    discover_sim_output_manifest,
    parse_video_manifest,
)


def test_manifest_returns_group_videos_in_episode_order(tmp_path: Path) -> None:
    manifest = parse_video_manifest(
        {
            "study_id": "pilot",
            "videos": [
                {
                    "video_id": "second",
                    "path": "second.mp4",
                    "policy_id": "policy_a",
                    "viewpoint": "first_person",
                    "robot_id": "g1",
                    "episode_id": "g1_point_to_point_static_obstacles",
                    "group_ids": ["policy_a_fp"],
                    "episode_order": 2,
                },
                {
                    "video_id": "first",
                    "path": "first.mp4",
                    "policy_id": "policy_a",
                    "viewpoint": "first_person",
                    "robot_id": "g1",
                    "episode_id": "g1_point_to_point_open",
                    "group_ids": ["policy_a_fp"],
                    "episode_order": 1,
                },
            ],
        },
        video_root=tmp_path,
    )

    assert [video.video_id for video in manifest.videos_for_group("policy_a_fp")] == [
        "first",
        "second",
    ]


def test_optional_go2_entries_do_not_affect_required_group(tmp_path: Path) -> None:
    manifest = parse_video_manifest(
        {
            "videos": [
                {
                    "video_id": "go2-first",
                    "path": "go2.mp4",
                    "policy_id": "policy_a",
                    "viewpoint": "first_person",
                    "robot_id": "go2",
                    "episode_id": "go2_point_to_point_open",
                    "group_ids": ["go2_policy_a_fp"],
                }
            ]
        },
        video_root=tmp_path,
    )

    assert manifest.videos_for_group("policy_a_fp") == ()


def test_manifest_rejects_paths_outside_video_root(tmp_path: Path) -> None:
    with pytest.raises(VideoManifestError):
        parse_video_manifest(
            {
                "videos": [
                    {
                        "video_id": "escape",
                        "path": "../escape.mp4",
                        "policy_id": "policy_a",
                        "viewpoint": "first_person",
                        "robot_id": "g1",
                        "episode_id": "g1_point_to_point_open",
                        "group_ids": ["policy_a_fp"],
                    }
                ]
            },
            video_root=tmp_path,
        )


def test_manifest_parses_prediction_source_under_artifact_root(tmp_path: Path) -> None:
    manifest = parse_video_manifest(
        {
            "videos": [
                {
                    "video_id": "with-prediction",
                    "path": "video.mp4",
                    "policy_id": "policy_a",
                    "viewpoint": "first_person",
                    "robot_id": "g1",
                    "episode_id": "g1_point_to_point_open",
                    "group_ids": ["policy_a_fp"],
                    "prediction_source": {
                        "kind": "episode_metrics_csv",
                        "path": "run-1/episode-metrics-000.csv",
                        "run_id": "run-1",
                        "iteration": 0,
                    },
                }
            ]
        },
        video_root=tmp_path / "videos",
        artifact_root=tmp_path / "runs",
    )

    source = manifest.videos[0].prediction_source
    assert source is not None
    assert source.kind == "episode_metrics_csv"
    assert source.iteration == 0


def test_manifest_rejects_prediction_source_outside_artifact_root(tmp_path: Path) -> None:
    with pytest.raises(VideoManifestError, match="prediction source path"):
        parse_video_manifest(
            {
                "videos": [
                    {
                        "video_id": "escape",
                        "path": "video.mp4",
                        "policy_id": "policy_a",
                        "viewpoint": "first_person",
                        "robot_id": "g1",
                        "episode_id": "g1_point_to_point_open",
                        "group_ids": ["policy_a_fp"],
                        "prediction_source": {
                            "kind": "metrics_json",
                            "path": "../escape.json",
                        },
                    }
                ]
            },
            video_root=tmp_path / "videos",
            artifact_root=tmp_path / "runs",
        )


def test_discovers_sim_output_video_json_pair(tmp_path: Path) -> None:
    video_root = tmp_path / "videos"
    json_root = tmp_path / "json"
    video_path = video_root / "policy_a" / "arrival" / "g1_point_to_point_open.mp4"
    json_path = json_root / "policy_a" / "arrival" / "g1_point_to_point_open.json"
    video_path.parent.mkdir(parents=True)
    json_path.parent.mkdir(parents=True)
    video_path.write_bytes(b"fake")
    json_path.write_text(
        """
        {
          "episode_id": "g1_point_to_point_open",
          "source_episode_id": "g1_point_to_point_open",
          "robot_id": "g1",
          "policy_id": "policy_a",
          "camera_view": "arrival"
        }
        """,
        encoding="utf-8",
    )

    manifest = discover_sim_output_manifest(
        study_id="pilot",
        video_root=video_root,
        json_root=json_root,
    )

    video = manifest.videos[0]
    assert video.video_id == "policy_a_fp_g1_point_to_point_open"
    assert video.path == "policy_a/arrival/g1_point_to_point_open.mp4"
    assert video.viewpoint == "first_person"
    assert video.group_ids == ("policy_a_fp",)
    assert video.metrics["source_episode_id"] == "g1_point_to_point_open"
    assert video.prediction_source is not None
    assert video.prediction_source.root == "survey_json_root"
    assert video.prediction_source.path == "policy_a/arrival/g1_point_to_point_open.json"


def test_discovers_go2_sim_output_only_when_enabled(tmp_path: Path) -> None:
    video_root = tmp_path / "videos"
    json_root = tmp_path / "json"
    video_path = video_root / "policy_a" / "bystander" / "go2_point_to_point_open.mp4"
    json_path = json_root / "policy_a" / "bystander" / "go2_point_to_point_open.json"
    video_path.parent.mkdir(parents=True)
    json_path.parent.mkdir(parents=True)
    video_path.write_bytes(b"fake")
    json_path.write_text('{"robot_id": "go2"}', encoding="utf-8")

    required_manifest = discover_sim_output_manifest(
        study_id="pilot",
        video_root=video_root,
        json_root=json_root,
    )
    go2_manifest = discover_sim_output_manifest(
        study_id="pilot",
        video_root=video_root,
        json_root=json_root,
        include_go2=True,
    )

    assert required_manifest.videos == ()
    assert go2_manifest.videos[0].group_ids == ("go2_policy_a_bystander",)

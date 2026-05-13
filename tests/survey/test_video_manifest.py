from __future__ import annotations

from pathlib import Path

import pytest

from asimovbm.survey.video_manifest import VideoManifestError, parse_video_manifest


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
                    "episode_id": "g1_lateral_open",
                    "group_ids": ["policy_a_fp"],
                    "episode_order": 2,
                },
                {
                    "video_id": "first",
                    "path": "first.mp4",
                    "policy_id": "policy_a",
                    "viewpoint": "first_person",
                    "robot_id": "g1",
                    "episode_id": "g1_approach_user",
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
                    "episode_id": "go2_approach_user",
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
                        "episode_id": "g1_approach_user",
                        "group_ids": ["policy_a_fp"],
                    }
                ]
            },
            video_root=tmp_path,
        )

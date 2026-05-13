from __future__ import annotations

import json
from pathlib import Path

import pytest

from asimovbm.local_runner.unity_runner import (
    UnityRunConfig,
    UnityRunnerError,
    build_unity_commands,
    discover_raw_unity_traces,
    find_unity_executable,
    run_unity_validation,
    to_windows_path,
)


def make_unity_project(tmp_path: Path) -> Path:
    project = tmp_path / "UnityProject"
    (project / "ProjectSettings").mkdir(parents=True)
    (project / "ProjectSettings" / "ProjectVersion.txt").write_text(
        "m_EditorVersion: 6000.4.6f1\n",
        encoding="utf-8",
    )
    return project


def raw_trace_payload() -> dict:
    return {
        "schema_version": "asimovbm.unity_trace.v1",
        "scene_id": "g1_real_motion",
        "episode_id": "g1_approach_user",
        "technical_valid": True,
        "terminal_status": "success",
        "metadata": {"start": [0.0, 0.0], "goal": [1.0, 0.0]},
        "steps": [
            {
                "step_id": 0,
                "time_s": 0.1,
                "dt_s": 0.1,
                "robot_pose": [0.0, 0.0, 0.0],
                "robot_velocity": [0.0, 0.0, 0.0],
                "action": [0.0, 0.0],
                "distance_to_goal": 1.0,
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
                "status": "success",
            },
        ],
    }


def test_to_windows_path_converts_mnt_paths() -> None:
    assert to_windows_path(Path("/mnt/d/_PROJECTS/Unity/AsimovBM")) == (
        "D:\\_PROJECTS\\Unity\\AsimovBM"
    )


def test_build_unity_commands_generates_then_runs_playmode_by_default(tmp_path: Path) -> None:
    project = make_unity_project(tmp_path)
    commands = build_unity_commands(
        UnityRunConfig(unity_project=project, artifact_root=tmp_path / "artifacts"),
        run_id="unity-smoke",
        unity_exe=Path("/mnt/c/Unity.exe"),
    )

    assert [command.name for command in commands] == ["generate-scenes", "playmode-tests"]
    assert commands[0].args[-1] == "AsimovBM.Editor.AsimovBatchRunner.GenerateScenes"
    assert "-quit" in commands[0].args
    assert "playmode" in commands[1].args
    assert "-quit" not in commands[1].args


def test_build_unity_commands_generates_scenes_when_tests_are_skipped(tmp_path: Path) -> None:
    project = make_unity_project(tmp_path)
    commands = build_unity_commands(
        UnityRunConfig(
            unity_project=project,
            artifact_root=tmp_path / "artifacts",
            skip_tests=True,
        ),
        run_id="unity-smoke",
        unity_exe=Path("/mnt/c/Unity.exe"),
    )

    assert [command.name for command in commands] == ["generate-scenes"]
    assert commands[0].args[-1] == "AsimovBM.Editor.AsimovBatchRunner.GenerateScenes"
    assert "-quit" in commands[0].args


def test_discovers_raw_unity_traces(tmp_path: Path) -> None:
    project = make_unity_project(tmp_path)
    trace = project / "Temp/AsimovBMUnityTests/unity-playmode-test/g1/iteration-000/raw-unity-trace.json"
    trace.parent.mkdir(parents=True)
    trace.write_text(json.dumps(raw_trace_payload()), encoding="utf-8")

    assert discover_raw_unity_traces(UnityRunConfig(unity_project=project), run_id="run") == (trace,)


def test_run_unity_validation_dry_run_does_not_require_trace_files(tmp_path: Path) -> None:
    project = make_unity_project(tmp_path)
    result = run_unity_validation(
        UnityRunConfig(
            unity_project=project,
            unity_exe=Path("/mnt/c/Unity.exe"),
            artifact_root=tmp_path / "artifacts",
            run_id="dry",
            dry_run=True,
        )
    )

    assert result.run_id == "dry"
    assert result.ingest_result is None
    assert len(result.commands) == 2


def test_run_unity_validation_can_ingest_existing_raw_traces_when_tests_skipped(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project = make_unity_project(tmp_path)
    raw_root = tmp_path / "raw"
    raw_trace = raw_root / "g1/iteration-000/raw-unity-trace.json"
    raw_trace.parent.mkdir(parents=True)
    raw_trace.write_text(json.dumps(raw_trace_payload()), encoding="utf-8")
    calls: list[tuple[str, ...]] = []

    def fake_run(args, check):
        calls.append(tuple(args))

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr("asimovbm.local_runner.unity_runner.subprocess.run", fake_run)

    result = run_unity_validation(
        UnityRunConfig(
            unity_project=project,
            unity_exe=Path("/mnt/c/Unity.exe"),
            artifact_root=tmp_path / "artifacts",
            run_id="unity-smoke",
            skip_tests=True,
            raw_trace_root=raw_root,
        )
    )

    assert len(calls) == 1
    assert result.ingest_result is not None
    assert result.ingest_result.manifest_path.exists()


def test_find_unity_executable_reports_missing_env_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UNITY_EXE", str(tmp_path / "missing.exe"))

    with pytest.raises(UnityRunnerError, match="UNITY_EXE does not exist"):
        find_unity_executable(make_unity_project(tmp_path))

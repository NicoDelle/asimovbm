"""WSL-friendly Unity validation runner."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .unity_ingest import UnityIngestConfig, UnityIngestResult, ingest_unity_trace_files


class UnityRunnerError(RuntimeError):
    """Raised when Unity validation cannot run."""


@dataclass(frozen=True)
class UnityCommand:
    name: str
    args: tuple[str, ...]
    log_path: Path | None = None


@dataclass(frozen=True)
class UnityRunConfig:
    unity_project: Path
    artifact_root: Path = Path("artifacts/unity-validation")
    unity_exe: Path | None = None
    run_id: str | None = None
    dry_run: bool = False
    skip_tests: bool = False
    raw_trace_root: Path | None = None
    extra_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UnityRunResult:
    run_id: str
    commands: tuple[UnityCommand, ...]
    ingest_result: UnityIngestResult | None = None


def run_unity_validation(config: UnityRunConfig) -> UnityRunResult:
    run_id = config.run_id or _new_run_id()
    unity_exe = config.unity_exe or find_unity_executable(config.unity_project)
    commands = build_unity_commands(config, run_id=run_id, unity_exe=unity_exe)

    if config.dry_run:
        return UnityRunResult(run_id=run_id, commands=commands)

    if not config.skip_tests:
        _clear_previous_unity_test_traces(config)

    for command in commands:
        _run_command(command)

    _copy_unity_outputs(config, run_id=run_id)
    raw_traces = discover_raw_unity_traces(config, run_id=run_id)
    if not raw_traces:
        raise UnityRunnerError("Unity validation completed but no raw Unity traces were found")

    ingest_result = ingest_unity_trace_files(
        raw_traces,
        config=UnityIngestConfig(
            artifact_root=config.artifact_root,
            run_id=run_id,
            viewer_mode="unity_batchmode",
            extra_metadata={
                **config.extra_metadata,
                "unity_project": str(config.unity_project),
                "unity_exe": str(unity_exe),
                "unity_commands": [command.name for command in commands],
            },
        ),
    )
    return UnityRunResult(run_id=run_id, commands=commands, ingest_result=ingest_result)


def build_unity_commands(
    config: UnityRunConfig,
    *,
    run_id: str,
    unity_exe: Path,
) -> tuple[UnityCommand, ...]:
    project_path = to_windows_path(config.unity_project)
    unity_output_dir = config.unity_project / "Temp" / "AsimovBMUnityRuns" / run_id
    log_dir = unity_output_dir / "unity-logs"
    if config.skip_tests:
        return (
            UnityCommand(
                name="generate-scenes",
                args=(
                    str(unity_exe),
                    "-batchmode",
                    "-quit",
                    "-projectPath",
                    project_path,
                    "-logFile",
                    to_windows_path(log_dir / "generate-scenes.log"),
                    "-executeMethod",
                    "AsimovBM.Editor.AsimovBatchRunner.GenerateScenes",
                ),
                log_path=log_dir / "generate-scenes.log",
            ),
        )

    return (
        UnityCommand(
            name="generate-scenes",
            args=(
                str(unity_exe),
                "-batchmode",
                "-quit",
                "-projectPath",
                project_path,
                "-logFile",
                to_windows_path(log_dir / "generate-scenes.log"),
                "-executeMethod",
                "AsimovBM.Editor.AsimovBatchRunner.GenerateScenes",
            ),
            log_path=log_dir / "generate-scenes.log",
        ),
        UnityCommand(
            name="playmode-tests",
            args=(
                str(unity_exe),
                "-batchmode",
                "-projectPath",
                project_path,
                "-logFile",
                to_windows_path(log_dir / "playmode.log"),
                "-runTests",
                "-testPlatform",
                "playmode",
                "-testResults",
                to_windows_path(unity_output_dir / "unity-playmode-results.xml"),
            ),
            log_path=log_dir / "playmode.log",
        ),
    )


def discover_raw_unity_traces(config: UnityRunConfig, *, run_id: str) -> tuple[Path, ...]:
    roots = []
    if config.raw_trace_root is not None:
        roots.append(config.raw_trace_root)
    roots.extend(
        [
            config.unity_project / "Temp" / "AsimovBMUnityTests",
            config.unity_project / "Artifacts" / "AsimovBM" / "Unity" / run_id,
        ]
    )
    traces: list[Path] = []
    for root in roots:
        if root.exists():
            traces.extend(sorted(root.rglob("raw-unity-trace.json")))
    return tuple(dict.fromkeys(traces))


def _copy_unity_outputs(config: UnityRunConfig, *, run_id: str) -> None:
    source = config.unity_project / "Temp" / "AsimovBMUnityRuns" / run_id
    if not source.exists():
        return
    destination = config.artifact_root / run_id / "unity-output"
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def _clear_previous_unity_test_traces(config: UnityRunConfig) -> None:
    test_trace_root = config.unity_project / "Temp" / "AsimovBMUnityTests" / "unity-playmode-test"
    if test_trace_root.exists():
        shutil.rmtree(test_trace_root)


def find_unity_executable(unity_project: Path) -> Path:
    env = os.environ.get("UNITY_EXE")
    if env:
        path = Path(env)
        if path.exists():
            return path
        raise UnityRunnerError(f"UNITY_EXE does not exist: {path}")

    version = _unity_project_version(unity_project)
    candidates = []
    if version:
        candidates.append(Path(f"/mnt/c/Program Files/Unity/Hub/Editor/{version}/Editor/Unity.exe"))
    candidates.extend(sorted(Path("/mnt/c/Program Files/Unity/Hub/Editor").glob("*/Editor/Unity.exe")))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise UnityRunnerError("Unity executable not found. Pass --unity-exe or set UNITY_EXE.")


def to_windows_path(path: Path) -> str:
    path = path.expanduser()
    text = str(path)
    if text.startswith("/mnt/") and len(text) > 6 and text[6] == "/":
        drive = text[5].upper()
        return drive + ":\\" + text[7:].replace("/", "\\")
    return text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="asimovbm-unity")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run Unity scene validation and ingest traces")
    run_parser.add_argument("--unity-project", required=True, type=Path)
    run_parser.add_argument("--unity-exe", type=Path)
    run_parser.add_argument("--artifact-root", type=Path, default=Path("artifacts/unity-validation"))
    run_parser.add_argument("--run-id")
    run_parser.add_argument("--raw-trace-root", type=Path)
    run_parser.add_argument("--skip-tests", action="store_true")
    run_parser.add_argument("--dry-run", action="store_true")

    ingest_parser = subparsers.add_parser("ingest", help="Ingest one or more Unity raw traces")
    ingest_parser.add_argument("--trace", action="append", type=Path, required=True)
    ingest_parser.add_argument("--artifact-root", type=Path, default=Path("artifacts/unity-validation"))
    ingest_parser.add_argument("--run-id")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "ingest":
        result = ingest_unity_trace_files(
            tuple(args.trace),
            config=UnityIngestConfig(artifact_root=args.artifact_root, run_id=args.run_id),
        )
        print(f"unity ingest run: {result.run_id}")
        print(f"manifest: {result.manifest_path}")
        print(f"report: {result.report_path}")
        return 0

    result = run_unity_validation(
        UnityRunConfig(
            unity_project=args.unity_project,
            artifact_root=args.artifact_root,
            unity_exe=args.unity_exe,
            run_id=args.run_id,
            dry_run=args.dry_run,
            skip_tests=args.skip_tests,
            raw_trace_root=args.raw_trace_root,
        )
    )
    if args.dry_run:
        for command in result.commands:
            print(command.name + ": " + " ".join(command.args))
        return 0
    assert result.ingest_result is not None
    print(f"unity validation run: {result.run_id}")
    print(f"manifest: {result.ingest_result.manifest_path}")
    print(f"report: {result.ingest_result.report_path}")
    return 0


def _run_command(command: UnityCommand) -> None:
    if command.log_path is not None:
        command.log_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(command.args, check=False)
    if result.returncode != 0:
        raise UnityRunnerError(f"Unity command failed ({command.name}) with exit code {result.returncode}")


def _unity_project_version(unity_project: Path) -> str | None:
    version_path = unity_project / "ProjectSettings" / "ProjectVersion.txt"
    if not version_path.exists():
        return None
    for line in version_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("m_EditorVersion:"):
            return line.split(":", 1)[1].strip()
    return None


def _new_run_id() -> str:
    return f"unity-{datetime.now(tz=UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"


if __name__ == "__main__":
    raise SystemExit(main())

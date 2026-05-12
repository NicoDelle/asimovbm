"""Artifact writing helpers for local validation runs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ArtifactPaths:
    run_dir: Path
    manifest_path: Path


def prepare_run_dir(artifact_root: Path, run_id: str) -> ArtifactPaths:
    run_dir = artifact_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return ArtifactPaths(run_dir=run_dir, manifest_path=run_dir / "manifest.json")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def relative_to_run(path: Path, run_dir: Path) -> str:
    return path.relative_to(run_dir).as_posix()

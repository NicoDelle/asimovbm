from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from asimovbm_client.protocol import PackageSubmission


class PackageLoadError(ValueError):
    """Raised when local robot package structure is unusable."""


def load_robot_package(path: str | Path) -> PackageSubmission:
    root = Path(path)
    config_path = root if root.is_file() else root / "robot_package.json"
    if not config_path.exists():
        raise PackageLoadError(f"Missing robot package config: {config_path}")

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PackageLoadError(f"Malformed robot package config: {exc}") from exc

    _require_mapping(config, "model", config_path)
    _require_list(config, "sensors", config_path)
    _require_mapping(config, "action_mapping", config_path)

    model = dict(config["model"])
    if "path" in model:
        _require_relative_file(config_path.parent, model["path"], "model.path")

    sensors = [dict(sensor) for sensor in config["sensors"]]
    seen_names: set[str] = set()
    for sensor in sensors:
        name = sensor.get("name")
        kind = sensor.get("kind")
        if not isinstance(name, str) or not name:
            raise PackageLoadError("Every sensor must declare a non-empty name")
        if not isinstance(kind, str) or not kind:
            raise PackageLoadError(f"Sensor {name!r} must declare a kind")
        if name in seen_names:
            raise PackageLoadError(f"Duplicate sensor stream name: {name}")
        seen_names.add(name)

    action_mapping = dict(config["action_mapping"])
    joints = action_mapping.get("joints")
    if not isinstance(joints, list) or not joints:
        raise PackageLoadError("action_mapping.joints must be a non-empty list")

    visual_assets = [dict(asset) for asset in config.get("visual_assets", [])]
    for asset in visual_assets:
        if "path" in asset:
            _require_relative_file(config_path.parent, asset["path"], "visual_assets.path")

    return PackageSubmission(
        name=str(config.get("name") or config_path.parent.name),
        model=model,
        sensors=sensors,
        action_mapping=action_mapping,
        robot_metadata=dict(config.get("robot_metadata", {})),
        visual_assets=visual_assets,
    )


def _require_mapping(config: dict[str, Any], key: str, config_path: Path) -> None:
    if not isinstance(config.get(key), dict):
        raise PackageLoadError(f"{config_path} must define object field {key!r}")


def _require_list(config: dict[str, Any], key: str, config_path: Path) -> None:
    if not isinstance(config.get(key), list):
        raise PackageLoadError(f"{config_path} must define list field {key!r}")


def _require_relative_file(root: Path, raw_path: object, field: str) -> None:
    if not isinstance(raw_path, str) or not raw_path:
        raise PackageLoadError(f"{field} must be a non-empty relative path")
    candidate = Path(raw_path)
    if candidate.is_absolute():
        raise PackageLoadError(f"{field} must be relative to the package directory")
    root_resolved = root.resolve()
    resolved = (root / candidate).resolve()
    if root_resolved != resolved and root_resolved not in resolved.parents:
        raise PackageLoadError(f"{field} must stay within the package directory")
    if not resolved.exists():
        raise PackageLoadError(f"Referenced {field} does not exist: {raw_path}")

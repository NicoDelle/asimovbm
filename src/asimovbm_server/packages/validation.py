"""Server-authoritative robot package validation.

Two distinct modes:

- ``validate_remote_manifest``: the client uploaded only manifest metadata
  inside a :class:`PackageSubmission`. The server validates manifest
  semantics and benchmark compatibility. It MUST NOT interpret any
  client-supplied path as a server filesystem path or read it from disk.

- ``validate_local_fixture_package``: a server-owned fixture directory
  (e.g. an example bundled with the deployment) is being validated.
  Filesystem checks apply, but only against ``fixture_root`` so traversal,
  absolute paths, and symlink escape are blocked.

The client's local loader (``asimovbm_client.robot_package.loader``) keeps
its convenience checks for participants, but the server is the
authoritative validator: the client's response is informational, and only
the server's :class:`PackageValidationResult` decides whether the control
loop runs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from asimovbm_protocol import PackageSubmission, ValidationResponse, ValidationStatus

# Reserved fields that would imply executable participant code on the server.
# They are not part of the v0 package contract and must be rejected.
RESERVED_EXECUTABLE_FIELDS: frozenset[str] = frozenset(
    {
        "executable",
        "executable_hook",
        "executable_hooks",
        "plugin",
        "plugins",
        "entry_point",
        "entry_points",
        "post_load_hook",
        "preload_hook",
    }
)

# Sensor kinds the v0 benchmark recognizes. Unknown kinds are accepted as
# manifest-level metadata only — they cannot influence server simulation.
KNOWN_SENSOR_KINDS: frozenset[str] = frozenset(
    {
        "lidar",
        "rgb",
        "depth",
        "proprioception",
        "robot_state",
        "imu",
        "tactile",
        "force_torque",
        "task_event",
    }
)

KNOWN_ACTION_MODES: frozenset[str] = frozenset({"joint_target"})


class PackageValidationError(ValueError):
    """Raised on a hard validation failure for server-local fixture packages."""


@dataclass(frozen=True)
class PackageValidationResult:
    """Outcome of server-side package validation.

    ``settings`` carries server-derived defaults (e.g. ``control_dt``) that
    flow back to the client through :class:`ValidationResponse`.
    """

    accepted: bool
    errors: tuple[str, ...] = ()
    settings: dict[str, Any] = field(default_factory=dict)

    def to_response(self) -> ValidationResponse:
        status = ValidationStatus.ACCEPTED if self.accepted else ValidationStatus.REJECTED
        return ValidationResponse(
            status=status,
            errors=list(self.errors),
            settings=dict(self.settings),
        )


# --------------------------------------------------------------------- helpers


def _check_reserved_executable_keys(payload: dict[str, Any], scope: str) -> list[str]:
    return [
        f"{scope}.{key}: executable hook fields are not part of the v0 package contract"
        for key in payload
        if key in RESERVED_EXECUTABLE_FIELDS
    ]


def _check_action_mapping(action_mapping: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    mode = action_mapping.get("mode")
    if not isinstance(mode, str) or mode not in KNOWN_ACTION_MODES:
        errors.append(
            f"action_mapping.mode must be one of {sorted(KNOWN_ACTION_MODES)}; got {mode!r}"
        )
    joints = action_mapping.get("joints")
    if not isinstance(joints, list) or not joints:
        errors.append("action_mapping.joints must be a non-empty list of joint names")
    else:
        for index, joint in enumerate(joints):
            if not isinstance(joint, str) or not joint:
                errors.append(f"action_mapping.joints[{index}] must be a non-empty string")
        if len(set(joints)) != len(joints):
            errors.append("action_mapping.joints must not contain duplicate names")
    errors.extend(_check_reserved_executable_keys(action_mapping, "action_mapping"))
    return errors


def _check_sensors(sensors: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    seen_names: set[str] = set()
    for index, sensor in enumerate(sensors):
        scope = f"sensors[{index}]"
        if not isinstance(sensor, dict):
            errors.append(f"{scope} must be an object")
            continue
        name = sensor.get("name")
        kind = sensor.get("kind")
        if not isinstance(name, str) or not name:
            errors.append(f"{scope}.name must be a non-empty string")
            continue
        if not isinstance(kind, str) or not kind:
            errors.append(f"{scope}.kind must be a non-empty string")
        if name in seen_names:
            errors.append(f"{scope}.name duplicates earlier sensor: {name!r}")
        seen_names.add(name)
        if isinstance(kind, str) and kind not in KNOWN_SENSOR_KINDS:
            # Unknown kinds are tolerated as metadata but flagged for review.
            errors.append(
                f"{scope}.kind {kind!r} is not in the v0 known kinds; "
                "manifest accepted but server simulation cannot generate this stream"
            )
        errors.extend(_check_reserved_executable_keys(sensor, scope))
    return errors


def _check_manifest_semantics(submission: PackageSubmission) -> list[str]:
    errors: list[str] = []
    if not isinstance(submission.name, str) or not submission.name:
        errors.append("name must be a non-empty string")
    if not isinstance(submission.model, dict) or not submission.model:
        errors.append("model must be a non-empty object")
    else:
        errors.extend(_check_reserved_executable_keys(submission.model, "model"))
        model_format = submission.model.get("format")
        if not isinstance(model_format, str) or not model_format:
            errors.append("model.format must be a non-empty string")
    if not isinstance(submission.sensors, list) or not submission.sensors:
        errors.append("sensors must be a non-empty list")
    else:
        errors.extend(_check_sensors(submission.sensors))
    if not isinstance(submission.action_mapping, dict):
        errors.append("action_mapping must be an object")
    else:
        errors.extend(_check_action_mapping(submission.action_mapping))
    if not isinstance(submission.robot_metadata, dict):
        errors.append("robot_metadata must be an object")
    else:
        errors.extend(_check_reserved_executable_keys(submission.robot_metadata, "robot_metadata"))
    if not isinstance(submission.visual_assets, list):
        errors.append("visual_assets must be a list")
    return errors


# ----------------------------------------------------------- public validators


def validate_remote_manifest(
    submission: PackageSubmission,
    *,
    server_settings: dict[str, Any] | None = None,
) -> PackageValidationResult:
    """Validate a remote-submitted manifest without touching the filesystem.

    Client-supplied paths are NEVER opened or stat'd. The server only checks
    manifest semantics and benchmark compatibility.
    """
    errors = tuple(_check_manifest_semantics(submission))
    return PackageValidationResult(
        accepted=not errors,
        errors=errors,
        settings=dict(server_settings or {}),
    )


def _safe_relative_join(fixture_root: Path, raw_path: object, scope: str) -> tuple[Path | None, str | None]:
    if not isinstance(raw_path, str) or not raw_path:
        return None, f"{scope} must be a non-empty relative path"
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return None, f"{scope} must be relative to the fixture directory"
    fixture_resolved = fixture_root.resolve(strict=False)
    unresolved = fixture_root / candidate
    # Check the unresolved path for symlink-ness BEFORE resolving so a
    # symlink whose target is outside the fixture directory is detected.
    if unresolved.is_symlink():
        link_target = Path(os.readlink(unresolved))
        if not link_target.is_absolute():
            link_target = (unresolved.parent / link_target)
        link_resolved = link_target.resolve(strict=False)
        try:
            link_resolved.relative_to(fixture_resolved)
        except ValueError:
            return None, f"{scope} symlink escapes the fixture directory"
    target = unresolved.resolve(strict=False)
    try:
        target.relative_to(fixture_resolved)
    except ValueError:
        return None, f"{scope} escapes the fixture directory"
    if not target.exists():
        return None, f"{scope} references missing asset: {raw_path}"
    return target, None


def validate_local_fixture_package(
    submission: PackageSubmission,
    fixture_root: Path,
    *,
    server_settings: dict[str, Any] | None = None,
) -> PackageValidationResult:
    """Validate a server-owned fixture directory.

    Filesystem checks are confined to ``fixture_root``: absolute paths,
    parent-traversal (``..``), and symlinks pointing outside the root are
    rejected. ``fixture_root`` must point at the directory containing the
    fixture's ``robot_package.json``; this function does not interpret any
    client-supplied root.
    """
    errors = list(_check_manifest_semantics(submission))

    fixture_root = Path(fixture_root)
    if not fixture_root.is_dir():
        errors.append(f"fixture_root must be an existing directory: {fixture_root}")
        return PackageValidationResult(
            accepted=False,
            errors=tuple(errors),
            settings=dict(server_settings or {}),
        )

    model_path = submission.model.get("path") if isinstance(submission.model, dict) else None
    if model_path is not None:
        _, message = _safe_relative_join(fixture_root, model_path, "model.path")
        if message is not None:
            errors.append(message)

    for index, asset in enumerate(submission.visual_assets):
        if not isinstance(asset, dict):
            continue
        asset_path = asset.get("path")
        if asset_path is None:
            continue
        _, message = _safe_relative_join(
            fixture_root, asset_path, f"visual_assets[{index}].path"
        )
        if message is not None:
            errors.append(message)

    return PackageValidationResult(
        accepted=not errors,
        errors=tuple(errors),
        settings=dict(server_settings or {}),
    )

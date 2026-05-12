"""Server-authoritative package validation tests.

Covers:

- happy path: minimal current-format package validates remotely and locally
- happy path: visual_assets metadata preserved
- error path: missing fields, malformed sensors, duplicate names, executable
  hook fields, empty joints, unknown action mode
- error path: server-local fixture rejects absolute path, parent traversal,
  symlink escape, missing asset
- isolation: remote manifest validation never reads client-supplied paths
"""

from __future__ import annotations

import os
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from asimovbm_protocol import PackageSubmission, ValidationStatus
from asimovbm_server.packages import (
    PackageValidationResult,
    validate_local_fixture_package,
    validate_remote_manifest,
)


def _minimal_submission(**overrides) -> PackageSubmission:
    defaults: dict = {
        "name": "testbot",
        "model": {"format": "mjcf", "path": "robot.xml"},
        "sensors": [
            {"name": "lidar_front", "kind": "lidar", "frequency_hz": 10},
            {"name": "proprioception", "kind": "proprioception", "frequency_hz": 40},
        ],
        "action_mapping": {"mode": "joint_target", "joints": ["left_wheel", "right_wheel"]},
        "robot_metadata": {"forward_axis": "x+"},
        "visual_assets": [],
    }
    defaults.update(overrides)
    return PackageSubmission(**defaults)


def _write_fixture(root: Path, *, with_visual: bool = False) -> None:
    (root / "robot.xml").write_text("<mujoco/>", encoding="utf-8")
    if with_visual:
        (root / "render.glb").write_text("placeholder", encoding="utf-8")


# --- happy paths ----------------------------------------------------------


def test_minimal_submission_validates_remotely() -> None:
    result = validate_remote_manifest(_minimal_submission())
    assert result.accepted, result.errors
    response = result.to_response()
    assert response.status == ValidationStatus.ACCEPTED
    assert response.errors == []


def test_minimal_fixture_validates_locally() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_fixture(root)
        result = validate_local_fixture_package(_minimal_submission(), root)
    assert result.accepted, result.errors


def test_visual_assets_metadata_preserved() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_fixture(root, with_visual=True)
        submission = _minimal_submission(
            visual_assets=[{"kind": "render_mesh", "path": "render.glb"}]
        )
        result = validate_local_fixture_package(submission, root)
    assert result.accepted, result.errors


def test_settings_flow_through_to_response() -> None:
    result = validate_remote_manifest(
        _minimal_submission(), server_settings={"control_dt": 0.025}
    )
    response = result.to_response()
    assert response.settings == {"control_dt": 0.025}


# --- manifest-level errors -----------------------------------------------


def test_missing_name_rejected() -> None:
    result = validate_remote_manifest(_minimal_submission(name=""))
    assert not result.accepted
    assert any("name" in err for err in result.errors)


def test_missing_model_format_rejected() -> None:
    result = validate_remote_manifest(_minimal_submission(model={"path": "robot.xml"}))
    assert not result.accepted
    assert any("model.format" in err for err in result.errors)


def test_empty_sensors_list_rejected() -> None:
    result = validate_remote_manifest(_minimal_submission(sensors=[]))
    assert not result.accepted


def test_duplicate_sensor_names_rejected() -> None:
    result = validate_remote_manifest(
        _minimal_submission(
            sensors=[
                {"name": "lidar", "kind": "lidar"},
                {"name": "lidar", "kind": "lidar"},
            ]
        )
    )
    assert not result.accepted
    assert any("duplicates" in err for err in result.errors)


def test_unknown_action_mode_rejected() -> None:
    result = validate_remote_manifest(
        _minimal_submission(action_mapping={"mode": "raw_torque", "joints": ["x"]})
    )
    assert not result.accepted
    assert any("action_mapping.mode" in err for err in result.errors)


def test_mobile_base_velocity_action_mode_is_accepted() -> None:
    result = validate_remote_manifest(
        _minimal_submission(
            action_mapping={
                "mode": "mobile_base_velocity",
                "joints": ["linear_velocity", "yaw_rate"],
            }
        )
    )
    assert result.accepted


def test_empty_joints_rejected() -> None:
    result = validate_remote_manifest(
        _minimal_submission(action_mapping={"mode": "joint_target", "joints": []})
    )
    assert not result.accepted
    assert any("joints" in err for err in result.errors)


def test_duplicate_joints_rejected() -> None:
    result = validate_remote_manifest(
        _minimal_submission(
            action_mapping={"mode": "joint_target", "joints": ["wheel", "wheel"]}
        )
    )
    assert not result.accepted
    assert any("duplicate" in err.lower() for err in result.errors)


def test_executable_hook_field_rejected_in_model() -> None:
    result = validate_remote_manifest(
        _minimal_submission(
            model={"format": "mjcf", "path": "robot.xml", "plugin": "danger.so"}
        )
    )
    assert not result.accepted
    assert any("executable hook" in err for err in result.errors)


def test_executable_hook_field_rejected_in_sensor() -> None:
    result = validate_remote_manifest(
        _minimal_submission(
            sensors=[
                {"name": "lidar", "kind": "lidar", "executable_hook": "x.py"},
            ]
        )
    )
    assert not result.accepted
    assert any("executable hook" in err for err in result.errors)


def test_unknown_sensor_kind_flagged_but_other_checks_continue() -> None:
    result = validate_remote_manifest(
        _minimal_submission(
            sensors=[
                {"name": "thermal", "kind": "thermal_camera"},
            ]
        )
    )
    assert not result.accepted
    assert any("not in the v0 known kinds" in err for err in result.errors)


# --- fixture-mode filesystem errors --------------------------------------


def test_fixture_rejects_absolute_model_path() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_fixture(root)
        absolute = str(root / "robot.xml")
        submission = _minimal_submission(model={"format": "mjcf", "path": absolute})
        result = validate_local_fixture_package(submission, root)
    assert not result.accepted
    assert any("relative" in err for err in result.errors)


def test_fixture_rejects_parent_traversal() -> None:
    with TemporaryDirectory() as tmp:
        outer = Path(tmp)
        inner = outer / "fixture"
        inner.mkdir()
        (outer / "leak.xml").write_text("leak", encoding="utf-8")
        submission = _minimal_submission(model={"format": "mjcf", "path": "../leak.xml"})
        result = validate_local_fixture_package(submission, inner)
    assert not result.accepted
    assert any("escapes" in err for err in result.errors)


def test_fixture_rejects_missing_asset() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        # No robot.xml on disk, but manifest references it.
        submission = _minimal_submission()
        result = validate_local_fixture_package(submission, root)
    assert not result.accepted
    assert any("missing asset" in err for err in result.errors)


@pytest.mark.skipif(
    sys.platform == "win32", reason="symlink escape test relies on POSIX symlinks"
)
def test_fixture_rejects_symlink_escape() -> None:
    with TemporaryDirectory() as tmp:
        outer = Path(tmp)
        secret = outer / "secret.xml"
        secret.write_text("top secret", encoding="utf-8")
        fixture = outer / "fixture"
        fixture.mkdir()
        link = fixture / "robot.xml"
        os.symlink(secret, link)
        submission = _minimal_submission(model={"format": "mjcf", "path": "robot.xml"})
        result = validate_local_fixture_package(submission, fixture)
    assert not result.accepted
    assert any("symlink" in err for err in result.errors)


def test_fixture_rejects_missing_root() -> None:
    submission = _minimal_submission()
    result = validate_local_fixture_package(submission, Path("/nonexistent/path/asimov"))
    assert not result.accepted


# --- remote isolation -----------------------------------------------------


def test_remote_validation_does_not_read_client_paths(tmp_path, monkeypatch) -> None:
    """Even if the manifest carries an absolute path, remote mode never opens it."""
    forbidden_calls: list[str] = []

    real_open = open

    def tracking_open(file, *args, **kwargs):  # type: ignore[no-untyped-def]
        forbidden_calls.append(str(file))
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr("builtins.open", tracking_open)

    submission = _minimal_submission(
        model={"format": "mjcf", "path": "/etc/passwd"},
        visual_assets=[{"kind": "render_mesh", "path": "/etc/shadow"}],
    )
    result = validate_remote_manifest(submission)
    # Remote mode validates manifest semantics. Both paths are absolute strings;
    # remote mode only cares about types, not filesystem state.
    assert result.accepted, result.errors
    assert "/etc/passwd" not in forbidden_calls
    assert "/etc/shadow" not in forbidden_calls


def test_validation_result_is_immutable_dataclass() -> None:
    result = PackageValidationResult(accepted=True)
    with pytest.raises(FrozenInstanceError):
        result.accepted = False  # type: ignore[misc]

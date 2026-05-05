"""Unit 0 import gate: planned package surfaces must import cleanly.

Optional MuJoCo/ONNX paths must surface a clear setup diagnostic when the
extras are not installed, never an import-time crash inside base server
imports.
"""

from __future__ import annotations

import importlib

import pytest


def test_asimovbm_client_imports() -> None:
    module = importlib.import_module("asimovbm_client")
    assert module is not None


def test_asimovbm_client_protocol_imports() -> None:
    module = importlib.import_module("asimovbm_client.protocol")
    assert module is not None


def test_asimovbm_protocol_package_importable() -> None:
    module = importlib.import_module("asimovbm_protocol")
    assert module is not None


def test_asimovbm_server_package_importable() -> None:
    module = importlib.import_module("asimovbm_server")
    assert module is not None


def test_g1_slam_pure_python_importable_without_mujoco() -> None:
    """Pure-Python g1_slam smoke modules must import without MuJoCo/ONNX."""
    simulation = importlib.import_module("g1_slam.simulation")
    assert hasattr(simulation, "run_navigation")
    geometry = importlib.import_module("g1_slam.geometry")
    assert hasattr(geometry, "Pose2D")


def test_optional_mujoco_runner_surface() -> None:
    """Importing the optional MuJoCo runner must either succeed or fail with
    a recognizable dependency error, not a silent attribute crash inside the
    server import path."""
    try:
        importlib.import_module("g1_slam.mujoco_runner")
    except ImportError as exc:
        message = str(exc).lower()
        assert "mujoco" in message or "module" in message
    except Exception as exc:  # pragma: no cover - defensive
        pytest.fail(
            f"optional g1_slam.mujoco_runner raised non-ImportError: {exc!r}"
        )

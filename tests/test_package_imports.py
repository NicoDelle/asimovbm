"""Import gate for active local-first package surfaces."""

from __future__ import annotations

import importlib

import pytest


def test_asimovbm_package_imports() -> None:
    module = importlib.import_module("asimovbm")
    assert module is not None


def test_asimovbm_metrics_imports() -> None:
    module = importlib.import_module("asimovbm.metrics")
    assert module is not None


def test_asimovbm_local_runner_imports() -> None:
    module = importlib.import_module("asimovbm.local_runner")
    assert module is not None


def test_asimovbm_reports_imports() -> None:
    module = importlib.import_module("asimovbm.reports")
    assert module is not None


def test_g1_slam_pure_python_importable_without_mujoco() -> None:
    """Pure-Python g1_slam smoke modules must import without MuJoCo/ONNX."""
    simulation = importlib.import_module("g1_slam.simulation")
    assert hasattr(simulation, "run_navigation")
    geometry = importlib.import_module("g1_slam.geometry")
    assert hasattr(geometry, "Pose2D")


def test_optional_mujoco_runner_surface() -> None:
    """Importing the optional MuJoCo runner must either succeed or fail with
    a recognizable dependency error, not a silent attribute crash."""
    try:
        importlib.import_module("g1_slam.mujoco_runner")
    except ImportError as exc:
        message = str(exc).lower()
        assert "mujoco" in message or "module" in message
    except Exception as exc:  # pragma: no cover - defensive
        pytest.fail(
            f"optional g1_slam.mujoco_runner raised non-ImportError: {exc!r}"
        )

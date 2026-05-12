from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from asimovbm_protocol import ActionMessage
from asimovbm_server.simulation import (
    MuJoCoAdapterConfig,
    MuJoCoSimulationAdapter,
    SimulationSetupError,
    SimulationStepError,
)

PACKAGE_ROOT = Path("examples/robot_packages/minimal")


def test_mujoco_adapter_missing_dependency_surfaces_setup_help(monkeypatch, tmp_path):
    real_import_module = importlib.import_module

    def fake_import_module(name: str, *args, **kwargs):
        if name == "mujoco":
            raise ModuleNotFoundError("mujoco")
        return real_import_module(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)

    with pytest.raises(SimulationSetupError, match=r"pip install -e '.\[g1-mujoco\]'"):
        MuJoCoSimulationAdapter(MuJoCoAdapterConfig(tmp_path / "robot.xml"))


def test_mujoco_adapter_emits_observations_and_applies_actions():
    pytest.importorskip("mujoco")
    adapter = MuJoCoSimulationAdapter(MuJoCoAdapterConfig(PACKAGE_ROOT / "robot.xml"))

    step = adapter.next_step()
    sensor_names = {sensor.name for sensor in step.sensors}

    assert {"pose", "proprioception", "lidar_front"} <= sensor_names
    adapter.apply_action(ActionMessage(step.step_id, [0.5, 0.0], latency_ms=1.0))

    report = adapter.smoke_result()
    assert report.maturity == "mujoco_mobile_base_smoke"
    assert report.steps == 1
    assert report.final_pose["x"] > 0.0


def test_mujoco_adapter_rejects_wrong_action_shape():
    pytest.importorskip("mujoco")
    adapter = MuJoCoSimulationAdapter(MuJoCoAdapterConfig(PACKAGE_ROOT / "robot.xml"))
    step = adapter.next_step()

    with pytest.raises(SimulationStepError, match=r"\[linear, yaw_rate\]"):
        adapter.apply_action(ActionMessage(step.step_id, [0.5], latency_ms=1.0))

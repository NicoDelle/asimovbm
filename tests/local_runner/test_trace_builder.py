from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from g1_slam.controller import PurePursuitConfig
from g1_slam.geometry import Pose2D
from g1_slam.world import World2D

import asimovbm.local_runner.backends as local_backends
import asimovbm.local_runner.real_backends as real_backends
from asimovbm.local_runner.backends import G1SlamReferenceBackend
from asimovbm.local_runner.catalog import LocalEpisodeSpec, load_default_catalog
from asimovbm.local_runner.real_backends import G1RoboJuDoRealTraceBackend
from g1_slam.config import (
    DynamicObstaclesConfig,
    LocomotionConfig,
    NavigationConfig,
    VisualizationConfig,
)


def test_reference_backend_records_step_measurements() -> None:
    spec = LocalEpisodeSpec(
        id="tiny_episode",
        title="Tiny episode",
        description="small enough for a unit test",
        path=Path("tiny.json"),
        checksum_sha256="abc123",
        raw_config={},
        config=NavigationConfig(
            start=Pose2D(0.0, 0.0, 0.0),
            goal=(0.1, 0.0),
            steps=5,
            controller=PurePursuitConfig(goal_tolerance=0.2),
            locomotion=LocomotionConfig(
                mode="kinematic",
                policy_path=None,
                robojudo_config="g1_asap_loco",
                observation_size=None,
                observation_profile="generic",
                action_scale=0.25,
                kp=35.0,
                kd=1.0,
            ),
            world=World2D(-1.0, -1.0, 1.0, 1.0, ()),
            dynamic_obstacles=DynamicObstaclesConfig(
                mode="none",
                blue_cylinders=False,
                blue_cylinder_seed=7,
                blue_cylinder_count=None,
                npc_policy="social_patrol",
                obstacles=(),
            ),
            visualization=VisualizationConfig(None, None, None, None, False, {}, False, 20),
        ),
        robot_id="g1",
        policy_id="g1_robojudo_asap",
        robot_selector="kinematic",
        canonical_backend_id="g1_slam_kinematic",
    )

    trace = G1SlamReferenceBackend().run_episode(spec, iteration=0, viewer_enabled=False)

    assert trace.technical_valid is True
    assert trace.terminal_status == "success"
    assert trace.steps
    assert trace.steps[0].public_observation["lidar_range_count"] == 181
    assert trace.viewer_mode == "headless"


def test_visible_viewer_failures_are_recorded_without_crashing_trace_collection(monkeypatch) -> None:
    spec = LocalEpisodeSpec(
        id="tiny_episode",
        title="Tiny episode",
        description="small enough for a unit test",
        path=Path("tiny.json"),
        checksum_sha256="abc123",
        raw_config={},
        config=NavigationConfig(
            start=Pose2D(0.0, 0.0, 0.0),
            goal=(0.1, 0.0),
            steps=5,
            controller=PurePursuitConfig(goal_tolerance=0.2),
            locomotion=LocomotionConfig(
                mode="kinematic",
                policy_path=None,
                robojudo_config="g1_asap_loco",
                observation_size=None,
                observation_profile="generic",
                action_scale=0.25,
                kp=35.0,
                kd=1.0,
            ),
            world=World2D(-1.0, -1.0, 1.0, 1.0, ()),
            dynamic_obstacles=DynamicObstaclesConfig(
                mode="none",
                blue_cylinders=False,
                blue_cylinder_seed=7,
                blue_cylinder_count=None,
                npc_policy="social_patrol",
                obstacles=(),
            ),
            visualization=VisualizationConfig(None, None, None, None, False, {}, False, 20),
        ),
        robot_id="g1",
        policy_id="g1_robojudo_asap",
        robot_selector="kinematic",
        canonical_backend_id="g1_slam_kinematic",
    )

    class FailedViewer:
        returncode = -11
        stderr = "core dumped"

    def fail_viewer(*args, **kwargs):
        return FailedViewer()

    monkeypatch.setattr(local_backends.subprocess, "run", fail_viewer)

    trace = G1SlamReferenceBackend().run_episode(spec, iteration=0, viewer_enabled=True)

    viewer_proof = trace.metadata["viewer_proof"]
    assert viewer_proof["viewer_status"] == "failed"
    assert viewer_proof["returncode"] == -11
    assert "core dumped" in viewer_proof["stderr_tail"]


def test_robojudo_viewer_receives_selected_policy_config(monkeypatch) -> None:
    spec = load_default_catalog().select(
        ("g1_point_to_point_open",),
        robot_id="g1",
        policy_id="g1_robojudo_unitree",
    )[0]
    captured = {}

    class SuccessfulViewer:
        returncode = 0
        stderr = ""

    def fake_viewer(command, **kwargs):
        captured["command"] = command
        return SuccessfulViewer()

    monkeypatch.setattr(local_backends.subprocess, "run", fake_viewer)

    viewer_proof = local_backends._run_viewer_subprocess(spec, viewer_speed=1.0, camera_view="arrival")

    command = captured["command"]
    assert command[command.index("--robojudo-config") + 1] == "g1"
    assert command[command.index("--camera-view") + 1] == "arrival"
    assert command[command.index("--start-delay") + 1] == "1.0"
    assert command[command.index("--start") + 1 : command.index("--start") + 4] == ["-2.5", "1.6", "0.35"]
    assert command[command.index("--goal") + 1 : command.index("--goal") + 3] == ["2.5", "1.6"]
    assert viewer_proof["robojudo_config"] == "g1"


def test_real_robojudo_backend_uses_child_trace_json_as_metric_source(monkeypatch) -> None:
    spec = load_default_catalog().select(
        ("g1_point_to_point_open",),
        robot_id="g1",
        policy_id="g1_robojudo_unitree",
    )[0]
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        trace_path = Path(command[command.index("--trace-path") + 1])
        trace_path.write_text(
            json.dumps(
                {
                    "schema": "asimovbm.sim_trace.v1",
                    "episode_id": spec.id,
                    "robot_id": "g1",
                    "policy_id": "robojudo:g1",
                    "status": "timeout",
                    "metadata": {
                        "trace_source": "viewer_loop",
                        "config_name": "g1",
                        "real_backend_verified": True,
                    },
                    "steps": [
                        {
                            "step_id": 1,
                            "time_s": 0.02,
                            "dt_s": 0.02,
                            "robot_pose": {"x": 0.0, "y": 0.0, "yaw": 0.0},
                            "robot_velocity": {"vx": 0.0, "vy": 0.0, "yaw_rate": 0.0},
                            "action": {"linear": 0.0, "yaw_rate": 0.0},
                            "distance_to_goal": 5.0,
                            "entities": [
                                {
                                    "id": "person_npc_0",
                                    "kind": "dynamic_obstacle",
                                    "type": "bystander",
                                    "pose": [0.4, 0.0, 0.0],
                                }
                            ],
                            "collisions": [
                                {
                                    "type": "contact",
                                    "category": "human",
                                    "geom1": "g1_base",
                                    "geom2": "person_npc_0",
                                }
                            ],
                            "contacts": [
                                {
                                    "category": "human",
                                    "geom1": "g1_base",
                                    "geom2": "person_npc_0",
                                }
                            ],
                            "qpos": [1.0, 2.0],
                            "qvel": [3.0],
                            "public_observation": {"distance_to_goal": 5.0},
                            "status": "running",
                            "path": [[0.0, 0.0], [1.0, 0.0]],
                        },
                        {
                            "step_id": 2,
                            "time_s": 0.04,
                            "dt_s": 0.02,
                            "robot_pose": {"x": 0.1, "y": 0.0, "yaw": 0.0},
                            "robot_velocity": {"vx": 5.0, "vy": 0.0, "yaw_rate": 0.0},
                            "action": {"linear": 0.3, "yaw_rate": 0.0},
                            "distance_to_goal": 4.9,
                            "entities": [],
                            "collisions": [
                                {
                                    "type": "contact",
                                    "category": "human",
                                    "geom1": "person_npc_0",
                                    "geom2": "g1_base",
                                }
                            ],
                            "status": "running",
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="trace ok", stderr="")

    monkeypatch.setattr(real_backends.subprocess, "run", fake_run)

    trace = G1RoboJuDoRealTraceBackend().run_episode(
        spec,
        iteration=2,
        viewer_enabled=True,
        viewer_speed=4.0,
        camera_view="arrival",
    )

    command = captured["command"]
    assert "--render" in command
    assert command[command.index("--robojudo-config") + 1] == "g1"
    assert command[command.index("--camera-view") + 1] == "arrival"
    assert command[command.index("--trace-path") + 1].endswith("trace.json")
    assert trace.execution_backend_id == "g1_robojudo_mujoco_trace_v1"
    assert trace.metadata["trace_source"] == "viewer_loop"
    assert trace.metadata["real_backend_verified"] is True
    assert trace.metadata["viewer_proof"]["viewer_status"] == "launched"
    assert trace.steps[0].dynamic_entities[0]["type"] == "bystander"
    assert trace.steps[0].qpos == (1.0, 2.0)
    assert trace.steps[0].qvel == (3.0,)
    assert trace.steps[0].collisions[0]["event_key"] == "human|g1_base|person_npc_0"
    assert trace.steps[1].collisions == ()


def test_real_robojudo_backend_fails_if_child_does_not_write_trace(monkeypatch) -> None:
    spec = load_default_catalog().select(
        ("g1_point_to_point_open",),
        robot_id="g1",
        policy_id="g1_robojudo_unitree",
    )[0]

    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(real_backends.subprocess, "run", fake_run)

    with pytest.raises(local_backends.LocalTraceBackendError, match="did not write trace JSON"):
        G1RoboJuDoRealTraceBackend().run_episode(
            spec,
            iteration=0,
            viewer_enabled=True,
            viewer_speed=4.0,
            camera_view="arrival",
        )


def test_visible_viewer_timeout_decodes_byte_stderr(monkeypatch) -> None:
    spec = LocalEpisodeSpec(
        id="tiny_episode",
        title="Tiny episode",
        description="small enough for a unit test",
        path=Path("tiny.json"),
        checksum_sha256="abc123",
        raw_config={},
        config=NavigationConfig(
            start=Pose2D(0.0, 0.0, 0.0),
            goal=(0.1, 0.0),
            steps=5,
            controller=PurePursuitConfig(goal_tolerance=0.2),
            locomotion=LocomotionConfig(
                mode="kinematic",
                policy_path=None,
                robojudo_config="g1_asap_loco",
                observation_size=None,
                observation_profile="generic",
                action_scale=0.25,
                kp=35.0,
                kd=1.0,
            ),
            world=World2D(-1.0, -1.0, 1.0, 1.0, ()),
            dynamic_obstacles=DynamicObstaclesConfig(
                mode="none",
                blue_cylinders=False,
                blue_cylinder_seed=7,
                blue_cylinder_count=None,
                npc_policy="social_patrol",
                obstacles=(),
            ),
            visualization=VisualizationConfig(None, None, None, None, False, {}, False, 20),
        ),
        robot_id="g1",
        policy_id="g1_robojudo_asap",
        robot_selector="kinematic",
        canonical_backend_id="g1_slam_kinematic",
    )

    def timeout_viewer(*args, **kwargs):
        raise local_backends.subprocess.TimeoutExpired(cmd="viewer", timeout=1.0, stderr=b"byte stderr")

    monkeypatch.setattr(local_backends.subprocess, "run", timeout_viewer)

    trace = G1SlamReferenceBackend().run_episode(spec, iteration=0, viewer_enabled=True)

    viewer_proof = trace.metadata["viewer_proof"]
    assert viewer_proof["viewer_status"] == "timeout"
    assert viewer_proof["stderr_tail"] == "byte stderr"

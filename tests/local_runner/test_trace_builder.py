from __future__ import annotations

from pathlib import Path

from g1_slam.controller import PurePursuitConfig
from g1_slam.geometry import Pose2D
from g1_slam.world import World2D

import asimovbm.local_runner.backends as local_backends
from asimovbm.local_runner.backends import G1SlamReferenceBackend
from asimovbm.local_runner.catalog import LocalEpisodeSpec
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
            ),
            visualization=VisualizationConfig(None, None, None, None, False, False, 20),
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
            ),
            visualization=VisualizationConfig(None, None, None, None, False, False, 20),
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

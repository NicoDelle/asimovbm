from __future__ import annotations

from pathlib import Path

from g1_slam.controller import PurePursuitConfig
from g1_slam.geometry import Pose2D
from g1_slam.world import World2D

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
        robot_selector="kinematic",
        canonical_backend_id="g1_slam_kinematic",
    )

    trace = G1SlamReferenceBackend().run_episode(spec, iteration=0, viewer_enabled=False)

    assert trace.technical_valid is True
    assert trace.terminal_status == "success"
    assert trace.steps
    assert trace.steps[0].public_observation["lidar_range_count"] == 181
    assert trace.viewer_mode == "headless"
    assert trace.measurement_proof_level == "reference"
    assert trace.steps[0].measurement_source == "reference"


def test_reference_backend_samples_dynamic_entities_at_step_timestamp() -> None:
    spec = LocalEpisodeSpec(
        id="fast_npc_episode",
        title="Fast NPC episode",
        description="detects mismatched entity timestamps",
        path=Path("fast-npc.json"),
        checksum_sha256="abc123",
        raw_config={"dynamic_obstacles": {"mode": "npcs", "count": 1}},
        config=NavigationConfig(
            start=Pose2D(-3.8, 0.0, 0.0),
            goal=(4.2, 0.0),
            steps=2,
            controller=PurePursuitConfig(goal_tolerance=0.01),
            locomotion=LocomotionConfig(
                mode="kinematic",
                policy_path=None,
                observation_size=None,
                observation_profile="generic",
                action_scale=0.25,
                kp=35.0,
                kd=1.0,
            ),
            world=World2D(-5.2, -3.0, 5.5, 3.0, ()),
            dynamic_obstacles=DynamicObstaclesConfig(
                mode="npcs",
                blue_cylinders=False,
                blue_cylinder_seed=11,
                blue_cylinder_count=1,
                npc_policy="social_patrol",
            ),
            visualization=VisualizationConfig(None, None, None, None, False, False, 20),
        ),
        robot_selector="kinematic",
        canonical_backend_id="g1_slam_kinematic",
        role_inventory=(
            {
                "id": "person_npc_0",
                "type": "human",
                "role": "bystander",
                "source": "dynamic_obstacle",
            },
        ),
    )
    backend = G1SlamReferenceBackend(dt_s=0.5)

    trace = backend.run_episode(spec, iteration=0, viewer_enabled=False)

    step = trace.steps[0]
    assert step.time_s == 0.5
    npc = step.dynamic_entities[0]
    assert npc["type"] == "human"
    assert npc["role"] == "bystander"
    assert npc["sample_time_s"] == step.time_s
    assert npc["pose"] != npc["metadata"]["debug_pose_at_step_start"]

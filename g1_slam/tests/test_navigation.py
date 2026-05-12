import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from g1_slam.__main__ import DEFAULT_GO2_POLICY_PATH, _fallback_missing_default_go2_policy
from g1_slam.config import LocomotionConfig, load_navigation_config
from g1_slam.dynamic_obstacles import (
    make_default_dynamic_cylinders,
    make_default_dynamic_obstacles,
    make_default_npcs,
    make_dynamic_cylinder_world,
)
from g1_slam.geometry import Pose2D
from g1_slam.lidar import simulate_lidar
from g1_slam.locomotion import _is_git_lfs_pointer
from g1_slam.mapping import GridSpec, OccupancyGrid
from g1_slam.mujoco_runner import _official_g1_scene_xml, _official_go2_scene_xml, _robot_spec
from g1_slam.planner import AStarPlanner
from g1_slam.robojudo_backend import _robojudo_navigation_scene_tail, _world_with_dynamic_obstacles
from g1_slam.simulation import run_navigation
from g1_slam.world import RectObstacle, World2D, default_world


class NavigationTests(unittest.TestCase):
    def test_load_navigation_config(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "navigation.json"
            path.write_text(
                """{
                    "start": {"x": 1.0, "y": 2.0, "yaw": 0.5},
                    "goal": {"x": 3.0, "y": 4.0},
                    "steps": 77,
                    "world": {
                        "x_min": -1.0,
                        "y_min": -2.0,
                        "x_max": 5.0,
                        "y_max": 6.0,
                        "obstacles": [
                            {"x_min": 0.0, "y_min": 0.1, "x_max": 0.2, "y_max": 0.3}
                        ]
                    },
                    "dynamic_obstacles": {
                        "mode": "npcs",
                        "seed": 42,
                        "count": 3,
                        "npc_policy": "social_patrol"
                    },
                    "visualization": {
                        "camera": {
                            "fixed": true,
                            "lookat": {"x": 1.0, "y": 2.0, "z": 1.2},
                            "distance": 3.5,
                            "azimuth": 90.0,
                            "elevation": -8.0
                        },
                        "show_trajectory": true,
                        "trajectory_interval_steps": 12
                    }
                }""",
                encoding="utf-8",
            )
            config = load_navigation_config(path)
        self.assertEqual(config.start, Pose2D(1.0, 2.0, 0.5))
        self.assertEqual(config.goal, (3.0, 4.0))
        self.assertEqual(config.steps, 77)
        self.assertIsNotNone(config.world)
        self.assertEqual(config.world.obstacles, (RectObstacle(0.0, 0.1, 0.2, 0.3),))
        self.assertEqual(config.dynamic_obstacles.mode, "npcs")
        self.assertFalse(config.dynamic_obstacles.blue_cylinders)
        self.assertEqual(config.dynamic_obstacles.blue_cylinder_seed, 42)
        self.assertEqual(config.dynamic_obstacles.blue_cylinder_count, 3)
        self.assertEqual(config.dynamic_obstacles.npc_policy, "social_patrol")
        self.assertEqual(config.visualization.camera_lookat, (1.0, 2.0, 1.2))
        self.assertEqual(config.visualization.camera_distance, 3.5)
        self.assertTrue(config.visualization.fixed_camera)
        self.assertTrue(config.visualization.show_trajectory)
        self.assertEqual(config.visualization.trajectory_interval_steps, 12)

    def test_default_go2_policy_placeholder_falls_back_to_kinematic_locomotion(self):
        config = LocomotionConfig(
            mode="policy",
            policy_path=DEFAULT_GO2_POLICY_PATH,
            observation_size=None,
            observation_profile="dias_ai_master_go2_velocity_flat",
            action_scale=0.5,
            kp=50.0,
            kd=3.5,
        )

        with patch.object(Path, "exists", return_value=False):
            fallback = _fallback_missing_default_go2_policy(
                config,
                robot="official_go2",
                explicit_policy_path=False,
            )

        self.assertEqual(fallback.mode, "kinematic")
        self.assertEqual(fallback.policy_path, DEFAULT_GO2_POLICY_PATH)

    def test_explicit_missing_go2_policy_does_not_fall_back(self):
        config = LocomotionConfig(
            mode="policy",
            policy_path=DEFAULT_GO2_POLICY_PATH,
            observation_size=None,
            observation_profile="dias_ai_master_go2_velocity_flat",
            action_scale=0.5,
            kp=50.0,
            kd=3.5,
        )

        with patch.object(Path, "exists", return_value=False):
            fallback = _fallback_missing_default_go2_policy(
                config,
                robot="official_go2",
                explicit_policy_path=True,
            )

        self.assertEqual(fallback.mode, "policy")

    def test_episode_configs_load(self):
        config_dir = Path(__file__).resolve().parents[1] / "config" / "episodes"
        config_paths = sorted(config_dir.glob("*.json"))
        self.assertEqual(len(config_paths), 6)
        configs = {path.stem: load_navigation_config(path) for path in config_paths}

        self.assertEqual(configs["g1_lateral_open"].world.obstacles, ())
        self.assertFalse(configs["g1_lateral_open"].dynamic_obstacles.blue_cylinders)
        self.assertTrue(configs["g1_lateral_static_dynamic_obstacles"].world.obstacles)
        self.assertEqual(
            configs["g1_lateral_static_dynamic_obstacles"].dynamic_obstacles.mode,
            "npcs",
        )
        self.assertEqual(
            configs["g1_lateral_static_dynamic_obstacles"].dynamic_obstacles.blue_cylinder_count,
            3,
        )
        self.assertEqual(configs["go2_lateral_open"].world.obstacles, ())
        self.assertEqual(configs["go2_lateral_open"].locomotion.mode, "policy")
        self.assertEqual(
            configs["go2_lateral_open"].locomotion.policy_path,
            DEFAULT_GO2_POLICY_PATH,
        )
        self.assertEqual(configs["go2_lateral_open"].locomotion.observation_size, 45)
        self.assertEqual(
            configs["go2_lateral_open"].locomotion.observation_profile,
            "dias_ai_master_go2_velocity_flat",
        )
        self.assertEqual(configs["go2_lateral_open"].locomotion.action_scale, 0.5)
        self.assertEqual(
            configs["go2_lateral_static_dynamic_obstacles"].dynamic_obstacles.mode,
            "npcs",
        )
        self.assertEqual(
            configs["go2_lateral_static_dynamic_obstacles"].dynamic_obstacles.blue_cylinder_count,
            3,
        )
        for config in configs.values():
            self.assertTrue(config.visualization.fixed_camera)
            self.assertFalse(config.visualization.show_trajectory)
        self.assertLess(configs["g1_approach_user"].goal[0], 0.0)
        self.assertLess(configs["go2_approach_user"].goal[0], 0.0)

    def test_robot_spec_supports_official_g1(self):
        spec = _robot_spec("official_g1")
        self.assertEqual(spec.default_model_path.name, "g1_nav_generated.xml")
        self.assertFalse(spec.use_physics_step)

    def test_robot_spec_supports_official_go2(self):
        spec = _robot_spec("official_go2")
        self.assertEqual(spec.default_model_path.name, "go2_nav_generated.xml")
        self.assertFalse(spec.use_physics_step)

    def test_official_g1_scene_keeps_navigation_world(self):
        xml = _official_g1_scene_xml(default_world())
        self.assertIn('<include file="g1_29dof.xml"/>', xml)
        self.assertIn('name="goal"', xml)
        self.assertIn('name="obs_0"', xml)

    def test_official_go2_scene_keeps_navigation_world_and_dynamic_cylinders(self):
        cylinders = make_default_dynamic_cylinders(seed=7)[:2]
        xml = _official_go2_scene_xml(default_world(), cylinders)
        self.assertIn('<include file="go2.xml"/>', xml)
        self.assertIn('name="goal"', xml)
        self.assertIn('name="obs_0"', xml)
        self.assertIn('name="blue_cylinder_0"', xml)
        self.assertIn('mocap="true"', xml)

    def test_robojudo_navigation_scene_can_include_dynamic_blue_cylinders(self):
        world = make_dynamic_cylinder_world()
        cylinders = make_default_dynamic_cylinders(seed=7)
        xml = _robojudo_navigation_scene_tail(world, cylinders)
        self.assertIn('name="blue_cylinder_0"', xml)
        self.assertIn('name="blue_cylinder_2"', xml)
        self.assertIn('mocap="true"', xml)
        self.assertIn('nav_dynamic_cylinder_mat', xml)
        self.assertNotIn('name="obs_0"', xml)

    def test_robojudo_navigation_scene_can_include_npcs(self):
        world = make_dynamic_cylinder_world()
        npcs = make_default_npcs(seed=7, world=world)
        xml = _robojudo_navigation_scene_tail(world, npcs)
        self.assertIn('name="person_npc_0"', xml)
        self.assertIn('name="person_npc_2"', xml)
        self.assertIn('type="capsule"', xml)
        self.assertIn('nav_npc_clothes_mat', xml)

    def test_dynamic_obstacles_extend_lidar_world_over_time(self):
        world = default_world()
        obstacles = make_default_dynamic_obstacles("npcs", seed=7, world=world)
        world_at_start = _world_with_dynamic_obstacles(world, obstacles, sim_time=0.0)
        world_later = _world_with_dynamic_obstacles(world, obstacles, sim_time=3.0)
        self.assertEqual(len(world_at_start.obstacles), len(world.obstacles) + len(obstacles))
        self.assertNotEqual(world_at_start.obstacles[-1], world_later.obstacles[-1])

    def test_dynamic_obstacle_patrols_do_not_cross_static_obstacles(self):
        world = World2D(
            -5.2,
            -3.0,
            5.5,
            3.0,
            (
                RectObstacle(-1.2, -2.1, -0.7, 0.5),
                RectObstacle(1.4, -0.5, 1.9, 2.0),
            ),
        )
        obstacles = make_default_dynamic_obstacles("npcs", seed=11, count=3, world=world)
        for obstacle in obstacles:
            for index in range(64):
                sim_time = obstacle.period_s * index / 64
                x, y = obstacle.xy_at(sim_time)
                self.assertFalse(world.is_occupied(x, y, margin=obstacle.radius + 0.10))

    def test_lidar_hits_obstacle_ahead(self):
        world = World2D(-2, -2, 4, 2, (RectObstacle(1.0, -0.4, 1.2, 0.4),))
        scan = simulate_lidar(world, Pose2D(0, 0, 0), num_rays=3, max_range=3.0)
        self.assertGreaterEqual(scan.ranges[1], 0.9)
        self.assertLessEqual(scan.ranges[1], 1.1)

    def test_planner_routes_around_known_wall(self):
        grid = OccupancyGrid(GridSpec(50, 30, 0.1, -1.0, -1.5))
        for y in range(0, 25):
            grid.log_odds[grid.index((20, y))] = 4.0
        planner = AStarPlanner(grid)
        path = planner.plan(Pose2D(-0.5, 0.0, 0.0), (2.5, 0.0))
        self.assertTrue(path)
        self.assertTrue(any(0.65 <= x <= 1.35 and y > 1.2 for x, y in path))
        self.assertTrue(all(not (0.85 <= x <= 1.15 and y < 1.0) for x, y in path))

    def test_navigation_reaches_default_goal(self):
        result = run_navigation(default_world(), steps=1200)
        self.assertTrue(result.reached_goal)

    def test_git_lfs_pointer_policy_detection(self):
        with TemporaryDirectory() as tmp:
            pointer = Path(tmp) / "policy.onnx"
            pointer.write_text(
                "version https://git-lfs.github.com/spec/v1\n"
                "oid sha256:fbb8b61b12f2cd44dfc889f33566a8be2438124efee88b60c700b9605a94187a\n"
                "size 14196\n",
                encoding="utf-8",
            )

            self.assertTrue(_is_git_lfs_pointer(pointer))


if __name__ == "__main__":
    unittest.main()

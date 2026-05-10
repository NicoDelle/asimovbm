import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from g1_slam.dynamic_obstacles import make_default_dynamic_cylinders, make_dynamic_cylinder_world
from g1_slam.geometry import Pose2D
from g1_slam.lidar import simulate_lidar
from g1_slam.mapping import GridSpec, OccupancyGrid
from g1_slam.mujoco_runner import _official_g1_scene_xml, _robot_spec
from g1_slam.planner import AStarPlanner
from g1_slam.robojudo_backend import _robojudo_navigation_scene_tail, _world_with_dynamic_cylinders
from g1_slam.simulation import run_navigation
from g1_slam.world import RectObstacle, World2D, default_world

from g1_slam.config import load_navigation_config


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
                        "blue_cylinders": true,
                        "blue_cylinder_seed": 42,
                        "blue_cylinder_count": 3
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
        self.assertTrue(config.dynamic_obstacles.blue_cylinders)
        self.assertEqual(config.dynamic_obstacles.blue_cylinder_seed, 42)
        self.assertEqual(config.dynamic_obstacles.blue_cylinder_count, 3)
        self.assertEqual(config.visualization.camera_lookat, (1.0, 2.0, 1.2))
        self.assertEqual(config.visualization.camera_distance, 3.5)
        self.assertTrue(config.visualization.fixed_camera)
        self.assertTrue(config.visualization.show_trajectory)
        self.assertEqual(config.visualization.trajectory_interval_steps, 12)

    def test_episode_configs_load(self):
        config_dir = Path(__file__).resolve().parents[1] / "config" / "episodes"
        config_paths = sorted(config_dir.glob("*.json"))
        self.assertEqual(len(config_paths), 3)
        configs = {path.stem: load_navigation_config(path) for path in config_paths}

        self.assertEqual(configs["g1_lateral_open"].world.obstacles, ())
        self.assertFalse(configs["g1_lateral_open"].dynamic_obstacles.blue_cylinders)
        self.assertTrue(configs["g1_lateral_static_dynamic_obstacles"].world.obstacles)
        self.assertTrue(
            configs["g1_lateral_static_dynamic_obstacles"].dynamic_obstacles.blue_cylinders
        )
        self.assertEqual(
            configs["g1_lateral_static_dynamic_obstacles"].dynamic_obstacles.blue_cylinder_count,
            3,
        )
        for config in configs.values():
            self.assertTrue(config.visualization.fixed_camera)
            self.assertFalse(config.visualization.show_trajectory)
        self.assertLess(configs["g1_approach_user"].goal[0], 0.0)

    def test_robot_spec_supports_official_g1(self):
        spec = _robot_spec("official_g1")
        self.assertEqual(spec.default_model_path.name, "g1_nav_generated.xml")
        self.assertFalse(spec.use_physics_step)

    def test_official_g1_scene_keeps_navigation_world(self):
        xml = _official_g1_scene_xml(default_world())
        self.assertIn('<include file="g1_29dof.xml"/>', xml)
        self.assertIn('name="goal"', xml)
        self.assertIn('name="obs_0"', xml)

    def test_robojudo_navigation_scene_can_include_dynamic_blue_cylinders(self):
        world = make_dynamic_cylinder_world()
        cylinders = make_default_dynamic_cylinders(seed=7)
        xml = _robojudo_navigation_scene_tail(world, cylinders)
        self.assertIn('name="blue_cylinder_0"', xml)
        self.assertIn('name="blue_cylinder_7"', xml)
        self.assertIn('mocap="true"', xml)
        self.assertIn('nav_dynamic_cylinder_mat', xml)
        self.assertNotIn('name="obs_0"', xml)

    def test_dynamic_cylinders_extend_lidar_world_over_time(self):
        world = default_world()
        cylinders = make_default_dynamic_cylinders(seed=7)
        world_at_start = _world_with_dynamic_cylinders(world, cylinders, sim_time=0.0)
        world_later = _world_with_dynamic_cylinders(world, cylinders, sim_time=3.0)
        self.assertEqual(len(world_at_start.obstacles), len(world.obstacles) + len(cylinders))
        self.assertNotEqual(world_at_start.obstacles[-1], world_later.obstacles[-1])

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


if __name__ == "__main__":
    unittest.main()

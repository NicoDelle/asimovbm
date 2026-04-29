import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from g1_slam.config import load_navigation_config
from g1_slam.geometry import Pose2D
from g1_slam.lidar import simulate_lidar
from g1_slam.mapping import GridSpec, OccupancyGrid
from g1_slam.mujoco_runner import _official_g1_scene_xml, _robot_spec
from g1_slam.planner import AStarPlanner
from g1_slam.simulation import run_navigation
from g1_slam.world import RectObstacle, World2D, default_world


class NavigationTests(unittest.TestCase):
    def test_load_navigation_config(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "navigation.json"
            path.write_text(
                '{"start": {"x": 1.0, "y": 2.0, "yaw": 0.5}, "goal": {"x": 3.0, "y": 4.0}, "steps": 77}',
                encoding="utf-8",
            )
            config = load_navigation_config(path)
        self.assertEqual(config.start, Pose2D(1.0, 2.0, 0.5))
        self.assertEqual(config.goal, (3.0, 4.0))
        self.assertEqual(config.steps, 77)

    def test_robot_spec_supports_official_g1(self):
        spec = _robot_spec("official_g1")
        self.assertEqual(spec.default_model_path.name, "g1_nav_generated.xml")
        self.assertFalse(spec.use_physics_step)

    def test_official_g1_scene_keeps_navigation_world(self):
        xml = _official_g1_scene_xml(default_world())
        self.assertIn('<include file="g1_29dof.xml"/>', xml)
        self.assertIn('name="goal"', xml)
        self.assertIn('name="obs_0"', xml)

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

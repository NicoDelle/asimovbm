from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .controller import PurePursuitConfig, PurePursuitController
from .geometry import Pose2D, distance_xy
from .lidar import simulate_lidar
from .mapping import GridSpec, OccupancyGrid
from .planner import AStarPlanner
from .world import World2D

DEFAULT_START_POSE = Pose2D(-4.2, -3.2, 0.0)


@dataclass(frozen=True)
class SimulationResult:
    reached_goal: bool
    steps: int
    pose: Pose2D
    trajectory: tuple[Pose2D, ...]
    grid: OccupancyGrid
    last_path: tuple[tuple[float, float], ...]


def make_grid_for_world(world: World2D, resolution: float = 0.10) -> OccupancyGrid:
    width = int((world.x_max - world.x_min) / resolution)
    height = int((world.y_max - world.y_min) / resolution)
    return OccupancyGrid(GridSpec(width, height, resolution, world.x_min, world.y_min))


def run_navigation(
    world: World2D,
    *,
    start: Pose2D | None = None,
    goal: tuple[float, float] = (6.2, 3.1),
    steps: int = 900,
    dt: float = 0.08,
    robot_radius: float = 0.20,
    grid: OccupancyGrid | None = None,
    controller_config: PurePursuitConfig | None = None,
) -> SimulationResult:
    pose = start or DEFAULT_START_POSE
    grid = grid or make_grid_for_world(world)
    planner = AStarPlanner(grid)
    controller = PurePursuitController(controller_config)
    trajectory: list[Pose2D] = [pose]
    path: list[tuple[float, float]] = []

    for step in range(steps):
        scan = simulate_lidar(world, pose)
        grid.update_from_scan(pose, scan)
        if step % 8 == 0 or not path or controller.waypoint_index >= len(path):
            path = planner.plan(pose, goal)
            controller.reset()

        command = controller.command(pose, path, goal)
        candidate = pose.moved(command.linear, command.yaw_rate, dt)
        if world.collides(candidate, robot_radius):
            candidate = pose.moved(0.0, 0.9, dt)
            controller.reset()
            path = []
        pose = candidate
        trajectory.append(pose)

        if distance_xy((pose.x, pose.y), goal) < controller.config.goal_tolerance:
            return SimulationResult(True, step + 1, pose, tuple(trajectory), grid, tuple(path))

    return SimulationResult(False, steps, pose, tuple(trajectory), grid, tuple(path))


def save_trajectory(path: str | Path, trajectory: tuple[Pose2D, ...]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="ascii") as fh:
        fh.write("step,x,y,yaw\n")
        for step, pose in enumerate(trajectory):
            fh.write(f"{step},{pose.x:.4f},{pose.y:.4f},{pose.yaw:.4f}\n")

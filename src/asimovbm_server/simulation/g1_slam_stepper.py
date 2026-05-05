"""Legacy policy-in-loop stepper around pure-Python ``g1_slam`` pieces.

This is retained as old smoke scaffolding only. G1 navigation/policy logic now
lives on the client side; server-owned benchmark simulation should use MuJoCo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import fsum
from pathlib import Path
from typing import Any

from g1_slam.controller import PurePursuitController
from g1_slam.geometry import Pose2D, clamp, distance_xy
from g1_slam.lidar import LaserScan, simulate_lidar
from g1_slam.planner import AStarPlanner
from g1_slam.simulation import make_grid_for_world
from g1_slam.world import World2D, default_world

from asimovbm_protocol import ActionMessage, SensorReading, StepMessage, TaskEvent
from g1_slam.config import DEFAULT_NAVIGATION_CONFIG, NavigationConfig, load_navigation_config

from .base import (
    SimulationSetupError,
    SimulationSmokeResult,
    SimulationStepError,
    pose_to_dict,
    summarize_trajectory,
)
from .g1_slam_adapter import DEFAULT_G1_NAVIGATION_CONFIG


@dataclass(frozen=True)
class G1SlamStepperConfig:
    config_path: Path | None = DEFAULT_G1_NAVIGATION_CONFIG
    max_steps: int | None = None
    dt: float = 0.08
    robot_radius: float = 0.20
    lidar_rays: int = 31


@dataclass(frozen=True)
class G1SlamStepOutcome:
    step_id: int
    pose: dict[str, float]
    action: list[float]
    collision: bool
    reached_goal: bool
    sim_time: float


@dataclass
class G1SlamStepper:
    """Small policy-in-loop boundary over the g1_slam navigation state.

    The action vector is interpreted as a kinematic smoke command:
    ``[linear_velocity, yaw_rate]``. This is not the full G1 joint contract;
    it is a backend proof that a client-provided action can advance real
    simulator state under server authority.
    """

    nav_config: NavigationConfig
    world: World2D = field(default_factory=default_world)
    config: G1SlamStepperConfig = field(default_factory=G1SlamStepperConfig)

    def __post_init__(self) -> None:
        self.pose: Pose2D = self.nav_config.start
        self.grid = make_grid_for_world(self.world)
        self.planner = AStarPlanner(self.grid)
        self.controller = PurePursuitController(self.nav_config.controller)
        self.trajectory: list[Pose2D] = [self.pose]
        self.outcomes: list[G1SlamStepOutcome] = []
        self.last_path: list[tuple[float, float]] = []
        self._awaiting_step_id: int | None = None
        self._latest_scan: LaserScan | None = None

    @classmethod
    def from_config(
        cls,
        config: G1SlamStepperConfig | None = None,
        *,
        world: World2D | None = None,
    ) -> G1SlamStepper:
        stepper_config = config or G1SlamStepperConfig()
        nav_config = _load_nav_config(stepper_config.config_path)
        return cls(nav_config, world or default_world(), stepper_config)

    @property
    def step_count(self) -> int:
        return len(self.outcomes)

    @property
    def sim_time(self) -> float:
        return self.step_count * self.config.dt

    @property
    def reached_goal(self) -> bool:
        return (
            distance_xy((self.pose.x, self.pose.y), self.nav_config.goal)
            <= self.nav_config.controller.goal_tolerance
        )

    @property
    def terminal(self) -> bool:
        max_steps = self.config.max_steps or self.nav_config.steps
        return self.reached_goal or self.step_count >= max_steps

    def next_step(self) -> StepMessage:
        if self.terminal:
            raise SimulationStepError("g1_slam stepper is already terminal")
        if self._awaiting_step_id is not None:
            raise SimulationStepError(
                f"step {self._awaiting_step_id} still needs an action"
            )

        step_id = self.step_count + 1
        scan = simulate_lidar(
            self.world,
            self.pose,
            num_rays=self.config.lidar_rays,
        )
        self._latest_scan = scan
        self.grid.update_from_scan(self.pose, scan)
        if step_id == 1 or step_id % 8 == 0 or not self.last_path:
            self.last_path = self.planner.plan(self.pose, self.nav_config.goal)
            self.controller.reset()
        recommended = self.controller.command(
            self.pose, self.last_path, self.nav_config.goal
        )
        self._awaiting_step_id = step_id
        return StepMessage(
            step_id=step_id,
            sim_time=self.sim_time,
            control_dt=self.config.dt,
            sensors=[
                SensorReading("pose", "proprioception", self._pose_sensor_data()),
                SensorReading("lidar", "lidar", _scan_summary(scan)),
                SensorReading(
                    "navigation_plan",
                    "planner",
                    {
                        "goal": {
                            "x": self.nav_config.goal[0],
                            "y": self.nav_config.goal[1],
                        },
                        "path_points": len(self.last_path),
                        "next_waypoint": list(self.last_path[0])
                        if self.last_path
                        else None,
                        "recommended_command": {
                            "linear": recommended.linear,
                            "yaw_rate": recommended.yaw_rate,
                        },
                    },
                ),
            ],
            task_events=[
                TaskEvent(
                    "come_here",
                    {
                        "goal": {
                            "x": self.nav_config.goal[0],
                            "y": self.nav_config.goal[1],
                        },
                        "distance": distance_xy(
                            (self.pose.x, self.pose.y), self.nav_config.goal
                        ),
                    },
                )
            ],
        )

    def apply_action(self, action: ActionMessage) -> G1SlamStepOutcome:
        if self._awaiting_step_id is None:
            raise SimulationStepError("next_step() must be called before apply_action()")
        if action.step_id != self._awaiting_step_id:
            raise SimulationStepError(
                f"action step_id {action.step_id} does not match pending "
                f"step {self._awaiting_step_id}"
            )
        if not action.valid:
            raise SimulationStepError(action.invalid_reason or "invalid action")
        if len(action.action) < 2:
            raise SimulationStepError("g1_slam smoke actions require [linear, yaw_rate]")

        linear = clamp(
            float(action.action[0]),
            -self.nav_config.controller.max_linear_speed,
            self.nav_config.controller.max_linear_speed,
        )
        yaw_rate = clamp(
            float(action.action[1]),
            -self.nav_config.controller.max_yaw_rate,
            self.nav_config.controller.max_yaw_rate,
        )
        candidate = self.pose.moved(linear, yaw_rate, self.config.dt)
        collision = self.world.collides(candidate, self.config.robot_radius)
        if not collision:
            self.pose = candidate
        self.trajectory.append(self.pose)
        outcome = G1SlamStepOutcome(
            step_id=action.step_id,
            pose=pose_to_dict(self.pose),
            action=[linear, yaw_rate],
            collision=collision,
            reached_goal=self.reached_goal,
            sim_time=(self.step_count + 1) * self.config.dt,
        )
        self.outcomes.append(outcome)
        self._awaiting_step_id = None
        return outcome

    def smoke_result(self) -> SimulationSmokeResult:
        return SimulationSmokeResult(
            maturity="g1_slam_policy_in_loop_smoke",
            reached_goal=self.reached_goal,
            steps=self.step_count,
            final_pose=pose_to_dict(self.pose),
            trajectory_summary=summarize_trajectory(self.trajectory),
            telemetry={
                "goal": {"x": self.nav_config.goal[0], "y": self.nav_config.goal[1]},
                "actions": [
                    {
                        "step_id": outcome.step_id,
                        "action": list(outcome.action),
                        "collision": outcome.collision,
                        "sim_time": outcome.sim_time,
                    }
                    for outcome in self.outcomes
                ],
                "last_scan": _scan_summary(self._latest_scan)
                if self._latest_scan is not None
                else None,
                "last_path": {
                    "points": len(self.last_path),
                    "first": list(self.last_path[0]) if self.last_path else None,
                    "last": list(self.last_path[-1]) if self.last_path else None,
                },
            },
        )

    def _pose_sensor_data(self) -> dict[str, Any]:
        return {
            **pose_to_dict(self.pose),
            "goal_distance": distance_xy((self.pose.x, self.pose.y), self.nav_config.goal),
            "step_count": self.step_count,
        }


def _load_nav_config(path: Path | None) -> NavigationConfig:
    if path is None:
        return DEFAULT_NAVIGATION_CONFIG
    path = Path(path)
    if not path.exists():
        raise SimulationSetupError(f"g1_slam config path does not exist: {path}")
    try:
        return load_navigation_config(path)
    except Exception as exc:
        raise SimulationSetupError(f"failed to load g1_slam config: {exc}") from exc


def _scan_summary(scan: LaserScan) -> dict[str, Any]:
    if not scan.ranges:
        return {"num_rays": 0, "min_range": None, "max_range": scan.max_range}
    return {
        "num_rays": len(scan.ranges),
        "min_range": min(scan.ranges),
        "max_range": scan.max_range,
        "mean_range": fsum(scan.ranges) / len(scan.ranges),
    }

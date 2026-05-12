"""Legacy batch telemetry adapter for the pure-Python ``g1_slam`` demo.

This is retained as old smoke scaffolding only. G1 navigation/policy logic now
lives on the client side; server-owned benchmark simulation should use MuJoCo.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from g1_slam.simulation import SimulationResult, run_navigation
from g1_slam.world import World2D, default_world

from g1_slam.config import DEFAULT_NAVIGATION_CONFIG, NavigationConfig, load_navigation_config

from .base import (
    SimulationSetupError,
    SimulationSmokeResult,
    pose_to_dict,
    summarize_trajectory,
)

DEFAULT_G1_NAVIGATION_CONFIG = Path("g1_slam/config/navigation.json")


@dataclass(frozen=True)
class G1SlamBatchConfig:
    config_path: Path | None = DEFAULT_G1_NAVIGATION_CONFIG
    steps: int | None = None
    dt: float = 0.08
    robot_radius: float = 0.20


class G1SlamBatchAdapter:
    """Run ``g1_slam.run_navigation`` and convert output to smoke telemetry."""

    maturity = "g1_slam_batch_smoke"

    def __init__(
        self,
        config: G1SlamBatchConfig | None = None,
        *,
        world: World2D | None = None,
    ) -> None:
        self.config = config or G1SlamBatchConfig()
        self.world = world or default_world()

    def run(self) -> SimulationSmokeResult:
        nav_config = self._load_config()
        result = run_navigation(
            self.world,
            start=nav_config.start,
            goal=nav_config.goal,
            steps=self.config.steps or nav_config.steps,
            dt=self.config.dt,
            robot_radius=self.config.robot_radius,
            controller_config=nav_config.controller,
        )
        return self._to_smoke_result(result, nav_config)

    def _load_config(self) -> NavigationConfig:
        path = self.config.config_path
        if path is None:
            return DEFAULT_NAVIGATION_CONFIG
        path = Path(path)
        if not path.exists():
            raise SimulationSetupError(f"g1_slam config path does not exist: {path}")
        try:
            return load_navigation_config(path)
        except Exception as exc:
            raise SimulationSetupError(f"failed to load g1_slam config: {exc}") from exc

    def _to_smoke_result(
        self,
        result: SimulationResult,
        nav_config: NavigationConfig,
    ) -> SimulationSmokeResult:
        return SimulationSmokeResult(
            maturity=self.maturity,
            reached_goal=result.reached_goal,
            steps=result.steps,
            final_pose=pose_to_dict(result.pose),
            trajectory_summary=summarize_trajectory(result.trajectory),
            telemetry={
                "goal": {"x": nav_config.goal[0], "y": nav_config.goal[1]},
                "grid": _grid_summary(result),
                "last_path": _path_summary(result.last_path),
                "controller": {
                    "goal_tolerance": nav_config.controller.goal_tolerance,
                    "max_linear_speed": nav_config.controller.max_linear_speed,
                    "max_yaw_rate": nav_config.controller.max_yaw_rate,
                },
            },
        )


def _grid_summary(result: SimulationResult) -> dict[str, Any]:
    spec = result.grid.spec
    occupied = sum(1 for value in result.grid.log_odds if value >= 0.8)
    observed = sum(1 for value in result.grid.log_odds if abs(value) > 0.1)
    return {
        "width": spec.width,
        "height": spec.height,
        "resolution": spec.resolution,
        "origin": {"x": spec.origin_x, "y": spec.origin_y},
        "occupied_cells": occupied,
        "observed_cells": observed,
    }


def _path_summary(path: tuple[tuple[float, float], ...]) -> dict[str, Any]:
    return {
        "points": len(path),
        "first": list(path[0]) if path else None,
        "last": list(path[-1]) if path else None,
    }

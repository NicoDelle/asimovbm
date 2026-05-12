"""Execution backends for local episode traces.

The default backend instruments the existing pure-Python `g1_slam` navigation
loop. It preserves the checked-in episode config, planner, lidar, dynamic
obstacle scripts, controller limits, and terminal semantics while producing the
per-step measurements that the metric bridge needs. Machines with full
RoboJuDo/Go2 assets can still use the canonical selectors recorded in the
manifest as release-smoke proof gates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from g1_slam.controller import PurePursuitController
from g1_slam.dynamic_obstacles import make_default_dynamic_obstacles, make_dynamic_cylinder_world
from g1_slam.geometry import Pose2D, distance_xy
from g1_slam.lidar import simulate_lidar
from g1_slam.planner import AStarPlanner
from g1_slam.simulation import make_grid_for_world
from g1_slam.world import World2D, default_world

from g1_slam.config import LocomotionConfig

from .catalog import LocalEpisodeSpec
from .traces import LocalEpisodeTrace, LocalStepTrace


class LocalTraceBackend(Protocol):
    backend_id: str

    def run_episode(
        self,
        spec: LocalEpisodeSpec,
        *,
        iteration: int,
        viewer_enabled: bool,
    ) -> LocalEpisodeTrace:
        ...


@dataclass(frozen=True)
class BackendProof:
    canonical_backend_id: str
    robot_selector: str
    execution_backend_id: str
    real_backend_verified: bool
    proof_status: str
    reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "canonical_backend_id": self.canonical_backend_id,
            "robot_selector": self.robot_selector,
            "execution_backend_id": self.execution_backend_id,
            "real_backend_verified": self.real_backend_verified,
            "proof_status": self.proof_status,
            "reason": self.reason,
        }


class G1SlamReferenceBackend:
    """Instrumented `g1_slam` navigation loop used for portable local traces."""

    backend_id = "g1_slam_reference_trace_v1"

    def __init__(self, *, dt_s: float = 0.08, robot_radius_m: float = 0.20) -> None:
        self.dt_s = dt_s
        self.robot_radius_m = robot_radius_m

    def run_episode(
        self,
        spec: LocalEpisodeSpec,
        *,
        iteration: int,
        viewer_enabled: bool,
    ) -> LocalEpisodeTrace:
        world = _episode_world(spec)
        dynamic_obstacles = _dynamic_obstacles(spec)
        viewer_proof = _maybe_run_real_viewer(spec, world, dynamic_obstacles, viewer_enabled)
        pose = spec.config.start
        goal = spec.config.goal
        grid = make_grid_for_world(world)
        planner = AStarPlanner(grid)
        controller = PurePursuitController(spec.config.controller)
        path: list[tuple[float, float]] = []
        step_traces: list[LocalStepTrace] = []
        terminal_status = "timeout"

        for step_id in range(spec.config.steps):
            time_s = step_id * self.dt_s
            active_world = _world_with_dynamic_obstacles(world, dynamic_obstacles, time_s)
            scan = simulate_lidar(active_world, pose)
            grid.update_from_scan(pose, scan)
            if step_id % 10 == 0 or not path or controller.waypoint_index >= len(path):
                path = planner.plan(pose, goal)
                controller.reset()

            command = controller.command(pose, path, goal)
            candidate = pose.moved(command.linear, command.yaw_rate, self.dt_s)
            collision = active_world.collides(candidate, self.robot_radius_m)
            if collision:
                candidate = pose.moved(0.0, spec.config.controller.max_yaw_rate * 0.65, self.dt_s)
                path = []
                controller.reset()
            velocity = _velocity_between(pose, candidate, self.dt_s)
            pose = candidate
            distance_to_goal = distance_xy((pose.x, pose.y), goal)
            status = "success" if distance_to_goal < spec.config.controller.goal_tolerance else "running"
            if status == "success":
                terminal_status = "success"
            step_traces.append(
                LocalStepTrace(
                    step_id=step_id,
                    time_s=time_s + self.dt_s,
                    dt_s=self.dt_s,
                    robot_pose=(pose.x, pose.y, pose.yaw),
                    robot_velocity=velocity,
                    action=(command.linear, command.yaw_rate),
                    distance_to_goal=distance_to_goal,
                    lidar_ranges=tuple(round(value, 4) for value in scan.ranges),
                    static_entities=_static_entities(world),
                    dynamic_entities=_dynamic_entities(dynamic_obstacles, time_s),
                    collisions=_collision_summary(collision, step_id),
                    public_observation={
                        "robot_pose": (pose.x, pose.y, pose.yaw),
                        "goal": goal,
                        "distance_to_goal": distance_to_goal,
                        "lidar_range_count": len(scan.ranges),
                    },
                    status=status,
                    metadata={"path_waypoints": len(path)},
                )
            )
            if status == "success":
                break

        return LocalEpisodeTrace(
            episode_id=spec.id,
            iteration=iteration,
            tier_id="g1_slam_canonical",
            technical_valid=True,
            terminal_status=terminal_status,
            steps=tuple(step_traces),
            config_checksum_sha256=spec.checksum_sha256,
            config_path=spec.path.as_posix(),
            robot_selector=spec.robot_selector,
            canonical_backend_id=spec.canonical_backend_id,
            execution_backend_id=self.backend_id,
            viewer_mode="visible" if viewer_enabled else "headless",
            metadata={
                "reference_backend": True,
                "viewer_proof": viewer_proof,
                "canonical_backend_proof": backend_proof_for(spec).to_dict(),
            },
        )


def backend_proof_for(spec: LocalEpisodeSpec) -> BackendProof:
    reason = (
        "portable local trace backend; run release smoke with RoboJuDo/Go2 assets "
        "to mark the canonical backend verified"
    )
    return BackendProof(
        canonical_backend_id=spec.canonical_backend_id,
        robot_selector=spec.robot_selector,
        execution_backend_id=G1SlamReferenceBackend.backend_id,
        real_backend_verified=False,
        proof_status="not_verified_in_this_run",
        reason=reason,
    )


def _episode_world(spec: LocalEpisodeSpec) -> World2D:
    if spec.config.world is not None:
        return spec.config.world
    if spec.config.dynamic_obstacles.mode != "none":
        return make_dynamic_cylinder_world()
    return default_world()


def _dynamic_obstacles(spec: LocalEpisodeSpec):
    config = spec.config.dynamic_obstacles
    if config.mode == "none":
        return ()
    return make_default_dynamic_obstacles(
        config.mode,
        seed=config.blue_cylinder_seed,
        count=config.blue_cylinder_count,
        world=spec.config.world,
        npc_policy=config.npc_policy,
    )


def _world_with_dynamic_obstacles(world: World2D, obstacles, sim_time: float) -> World2D:
    if not obstacles:
        return world
    return World2D(
        x_min=world.x_min,
        y_min=world.y_min,
        x_max=world.x_max,
        y_max=world.y_max,
        obstacles=world.obstacles + tuple(obstacle.rect_at(sim_time) for obstacle in obstacles),
    )


def _velocity_between(previous: Pose2D, current: Pose2D, dt_s: float) -> tuple[float, float, float]:
    return (
        (current.x - previous.x) / dt_s,
        (current.y - previous.y) / dt_s,
        (current.yaw - previous.yaw) / dt_s,
    )


def _static_entities(world: World2D) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "id": f"static_obstacle_{index}",
            "type": "obstacle",
            "shape": "rect",
            "bounds": (obstacle.x_min, obstacle.y_min, obstacle.x_max, obstacle.y_max),
        }
        for index, obstacle in enumerate(world.obstacles)
    )


def _dynamic_entities(obstacles, sim_time: float) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "id": obstacle.name,
            "type": "obstacle",
            "shape": "cylinder",
            "mode": obstacle.mode,
            "policy": obstacle.policy,
            "pose": (*obstacle.xy_at(sim_time), 0.0),
            "radius": obstacle.radius,
        }
        for obstacle in obstacles
    )


def _collision_summary(collision: bool, step_id: int) -> tuple[dict[str, object], ...]:
    if not collision:
        return ()
    return ({"step_id": step_id, "type": "world_collision"},)


def _maybe_run_real_viewer(
    spec: LocalEpisodeSpec,
    world: World2D,
    dynamic_obstacles,
    viewer_enabled: bool,
) -> dict[str, object]:
    if not viewer_enabled:
        return {"viewer_requested": False, "viewer_status": "not_requested"}
    try:
        if spec.locomotion_mode == "robojudo":
            return _run_robojudo_viewer(spec, world)
        return _run_mujoco_viewer(spec, world, dynamic_obstacles)
    except Exception as exc:
        return {
            "viewer_requested": True,
            "viewer_status": "not_launched",
            "reason": repr(exc),
        }


def _run_robojudo_viewer(spec: LocalEpisodeSpec, world: World2D) -> dict[str, object]:
    from g1_slam.robojudo_backend import RoboJuDoBackendConfig, run_robojudo_navigation

    run_robojudo_navigation(
        world,
        start=spec.config.start,
        goal=spec.config.goal,
        steps=spec.config.steps,
        controller_config=spec.config.controller,
        backend_config=RoboJuDoBackendConfig(
            max_vx=spec.config.controller.max_linear_speed,
            max_vy=spec.config.controller.max_linear_speed,
            max_yaw_rate=spec.config.controller.max_yaw_rate,
            run_fullspeed=False,
            enable_dynamic_cylinders=spec.config.dynamic_obstacles.blue_cylinders,
            dynamic_cylinder_seed=spec.config.dynamic_obstacles.blue_cylinder_seed,
            dynamic_cylinder_count=spec.config.dynamic_obstacles.blue_cylinder_count,
            dynamic_obstacle_mode=spec.config.dynamic_obstacles.mode,
            dynamic_obstacle_seed=spec.config.dynamic_obstacles.blue_cylinder_seed,
            dynamic_obstacle_count=spec.config.dynamic_obstacles.blue_cylinder_count,
            npc_policy=spec.config.dynamic_obstacles.npc_policy,
            visualization=spec.config.visualization,
        ),
    )
    return {"viewer_requested": True, "viewer_status": "launched", "path": "g1_robojudo"}


def _run_mujoco_viewer(spec: LocalEpisodeSpec, world: World2D, dynamic_obstacles) -> dict[str, object]:
    from g1_slam.mujoco_runner import run_mujoco_navigation

    run_mujoco_navigation(
        world,
        robot=spec.robot_selector,
        model_path=None,
        start=spec.config.start,
        goal=spec.config.goal,
        steps=spec.config.steps,
        controller_config=spec.config.controller,
        locomotion_config=_viewer_locomotion_config(spec),
        render=True,
        visualization_config=spec.config.visualization,
        dynamic_obstacles=dynamic_obstacles,
    )
    return {"viewer_requested": True, "viewer_status": "launched", "path": "mujoco"}


def _viewer_locomotion_config(spec: LocalEpisodeSpec) -> LocomotionConfig:
    if spec.locomotion_mode == "robojudo":
        return LocomotionConfig(
            mode="kinematic",
            policy_path=spec.config.locomotion.policy_path,
            observation_size=spec.config.locomotion.observation_size,
            observation_profile=spec.config.locomotion.observation_profile,
            action_scale=spec.config.locomotion.action_scale,
            kp=spec.config.locomotion.kp,
            kd=spec.config.locomotion.kd,
        )
    return spec.config.locomotion

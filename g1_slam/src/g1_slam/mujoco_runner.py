from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from math import cos, sin
from pathlib import Path
from time import sleep

from .config import LocomotionConfig, VisualizationConfig
from .controller import PurePursuitConfig, VelocityCommand
from .dynamic_obstacles import DynamicObstacle
from .geometry import Pose2D
from .scene_visuals import (
    dynamic_obstacle_scene_body,
    environment_scene_geoms,
    navigation_lights_and_camera,
    navigation_scene_assets,
    navigation_visual_settings,
    static_obstacle_geom,
)
from .simulation import make_grid_for_world
from .world import World2D

G1_SLAM_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class RobotSpec:
    name: str
    default_model_path: Path
    base_height: float
    use_physics_step: bool


ROBOT_SPECS = {
    "kinematic": RobotSpec(
        name="kinematic",
        default_model_path=G1_SLAM_ROOT / "assets" / "g1_kinematic.xml",
        base_height=0.72,
        use_physics_step=True,
    ),
    "official_g1": RobotSpec(
        name="official_g1",
        default_model_path=G1_SLAM_ROOT
        / "third_party"
        / "unitree_mujoco"
        / "unitree_robots"
        / "g1"
        / "g1_nav_generated.xml",
        base_height=0.80,
        use_physics_step=False,
    ),
    "official_go2": RobotSpec(
        name="official_go2",
        default_model_path=G1_SLAM_ROOT
        / "third_party"
        / "unitree_mujoco"
        / "unitree_robots"
        / "go2"
        / "go2_nav_generated.xml",
        base_height=0.27,
        use_physics_step=False,
    ),
}

_VIEWER_LIFETIME_GUARD: list[object] = []
DEFAULT_NAVIGATION_CONTROL_DT_S = 0.08


@dataclass(frozen=True)
class MujocoVideoRecord:
    output_path: Path
    frame_count: int
    control_dt_s: float
    duration_s: float


def run_mujoco_navigation(
    world: World2D,
    *,
    robot: str,
    model_path: str | Path | None,
    start: Pose2D,
    goal: tuple[float, float],
    steps: int,
    controller_config: PurePursuitConfig,
    locomotion_config: LocomotionConfig,
    render: bool,
    visualization_config: VisualizationConfig | None = None,
    dynamic_obstacles: tuple[DynamicObstacle, ...] = (),
    dynamic_cylinders: tuple[DynamicObstacle, ...] | None = None,
    realtime_factor: float = 1.0,
) -> None:
    if realtime_factor <= 0.0:
        raise ValueError("realtime_factor must be > 0")
    try:
        import mujoco
    except ModuleNotFoundError as exc:
        raise RuntimeError("Install mujoco to use --mujoco: pip install mujoco") from exc

    from .controller import PurePursuitController
    from .lidar import simulate_lidar
    from .locomotion import OnnxPolicyLocomotion
    from .planner import AStarPlanner

    if dynamic_cylinders is not None:
        dynamic_obstacles = dynamic_cylinders
    spec = _robot_spec(robot)
    resolved_model_path = _resolve_model_path(spec, model_path, world, dynamic_obstacles)
    model = mujoco.MjModel.from_xml_path(str(resolved_model_path))
    _suppress_robot_collision_visuals(mujoco, model, dynamic_obstacles)
    data = mujoco.MjData(model)
    _set_home_keyframe_pose(mujoco, model, data)
    _set_goal_marker(mujoco, model, data, goal)
    _set_dynamic_obstacle_positions(mujoco, model, data, dynamic_obstacles, 0.0)
    _set_freejoint_pose(mujoco, model, data, start, spec.base_height)
    mujoco.mj_forward(model, data)
    grid = make_grid_for_world(world)
    planner = AStarPlanner(grid)
    controller = PurePursuitController(controller_config)
    policy_locomotion = None
    if locomotion_config.mode == "policy":
        if spec.name not in {"official_g1", "official_go2"}:
            raise ValueError("locomotion.mode='policy' requires --robot official_g1 or official_go2")
        policy_locomotion = OnnxPolicyLocomotion(mujoco, model, locomotion_config)
        spec = RobotSpec(spec.name, spec.default_model_path, spec.base_height, True)
    elif locomotion_config.mode != "kinematic":
        raise ValueError("locomotion.mode must be 'kinematic' or 'policy'")
    pose = start
    path: list[tuple[float, float]] = []
    dt = model.opt.timestep

    viewer_context = _viewer(model, data) if render else _null_context()
    with viewer_context as viewer:
        if render:
            _configure_viewer_camera(viewer, visualization_config)
        for step in range(steps):
            sim_time = step * dt
            active_world = _world_with_dynamic_obstacles(world, dynamic_obstacles, sim_time)
            _set_dynamic_obstacle_positions(mujoco, model, data, dynamic_obstacles, sim_time)
            scan = simulate_lidar(active_world, pose)
            grid.update_from_scan(pose, scan)
            if step % 10 == 0 or not path or controller.waypoint_index >= len(path):
                path = planner.plan(pose, goal)
                controller.reset()

            if sim_time < controller.config.start_delay_s:
                command = VelocityCommand(0.0, 0.0)
            else:
                command = controller.command(pose, path, goal)
            candidate = pose.moved(command.linear, command.yaw_rate, dt)
            if active_world.collides(candidate, 0.20):
                candidate = pose.moved(0.0, 0.9, dt)
                path = []
                controller.reset()
            if policy_locomotion is None:
                pose = candidate
                _set_freejoint_pose(mujoco, model, data, pose, spec.base_height)
            else:
                policy_locomotion.step(data, command)

            if spec.use_physics_step:
                mujoco.mj_step(model, data)
                if policy_locomotion is not None:
                    pose = _read_freejoint_pose(mujoco, model, data, fallback=pose)
            else:
                mujoco.mj_forward(model, data)
            if render:
                viewer.sync()
                sleep(dt / realtime_factor)
    if render:
        # MuJoCo's passive viewer can segfault when the closed viewer object is
        # destroyed at function return on some Linux desktop stacks.
        _VIEWER_LIFETIME_GUARD.append((model, data, viewer_context, viewer))


def record_mujoco_navigation_video(
    world: World2D,
    *,
    robot: str,
    model_path: str | Path | None,
    start: Pose2D,
    goal: tuple[float, float],
    steps: int,
    controller_config: PurePursuitConfig,
    locomotion_config: LocomotionConfig,
    output_path: Path,
    visualization_config: VisualizationConfig | None = None,
    dynamic_obstacles: tuple[DynamicObstacle, ...] = (),
    fps: int = 12,
    width: int = 960,
    height: int = 540,
    control_dt_s: float = DEFAULT_NAVIGATION_CONTROL_DT_S,
    max_duration_s: float | None = None,
) -> MujocoVideoRecord:
    """Record the actual MuJoCo rendered scene for one navigation episode.

    Episode configs express `steps` in controller ticks, not raw MuJoCo physics
    ticks. Recording at the controller timestep prevents long episodes with
    start delays from being compressed into a couple seconds of physics time.
    """

    if fps < 1:
        raise ValueError("fps must be >= 1")
    if width < 1 or height < 1:
        raise ValueError("width and height must be positive")
    if control_dt_s <= 0.0:
        raise ValueError("control_dt_s must be > 0")
    if max_duration_s is not None and max_duration_s <= 0.0:
        raise ValueError("max_duration_s must be > 0 when provided")
    _ensure_offscreen_gl_backend()
    try:
        import mujoco
    except ModuleNotFoundError as exc:
        raise RuntimeError("Install mujoco to record MuJoCo survey videos") from exc

    from .controller import PurePursuitController
    from .lidar import simulate_lidar
    from .locomotion import OnnxPolicyLocomotion
    from .planner import AStarPlanner

    spec = _robot_spec(robot)
    resolved_model_path = _resolve_model_path(spec, model_path, world, dynamic_obstacles)
    model = mujoco.MjModel.from_xml_path(str(resolved_model_path))
    data = mujoco.MjData(model)
    _set_home_keyframe_pose(mujoco, model, data)
    _set_goal_marker(mujoco, model, data, goal)
    _set_dynamic_obstacle_positions(mujoco, model, data, dynamic_obstacles, 0.0)
    _set_freejoint_pose(mujoco, model, data, start, spec.base_height)
    mujoco.mj_forward(model, data)

    grid = make_grid_for_world(world)
    planner = AStarPlanner(grid)
    controller = PurePursuitController(controller_config)
    policy_locomotion = None
    if locomotion_config.mode == "policy":
        if spec.name not in {"official_g1", "official_go2"}:
            raise ValueError("locomotion.mode='policy' requires robot official_g1 or official_go2")
        policy_locomotion = OnnxPolicyLocomotion(mujoco, model, locomotion_config)
        spec = RobotSpec(spec.name, spec.default_model_path, spec.base_height, True)
    elif locomotion_config.mode != "kinematic":
        raise ValueError("locomotion.mode must be 'kinematic' or 'policy'")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    process = _open_ffmpeg_writer(output_path, fps=fps, width=width, height=height)
    renderer = mujoco.Renderer(model, height=height, width=width)
    camera = _offscreen_camera(mujoco, model, visualization_config)
    scene_option = _offscreen_scene_option(mujoco)
    pose = start
    path: list[tuple[float, float]] = []
    frame_count = 0
    render_stride = _render_stride(
        steps=steps,
        fps=fps,
        control_dt_s=control_dt_s,
        max_duration_s=max_duration_s,
    )

    renderer_closed = False
    try:
        _write_renderer_frame(renderer, data, camera, scene_option, process)
        frame_count += 1
        for step in range(steps):
            sim_time = step * control_dt_s
            frame_time = (step + 1) * control_dt_s
            should_render = (step + 1) % render_stride == 0 or step == steps - 1
            active_world = _world_with_dynamic_obstacles(world, dynamic_obstacles, sim_time)
            if policy_locomotion is not None:
                _set_dynamic_obstacle_positions(mujoco, model, data, dynamic_obstacles, sim_time)
            scan = simulate_lidar(active_world, pose)
            grid.update_from_scan(pose, scan)
            if step % 10 == 0 or not path or controller.waypoint_index >= len(path):
                path = planner.plan(pose, goal)
                controller.reset()

            if sim_time < controller.config.start_delay_s:
                command = VelocityCommand(0.0, 0.0)
            else:
                command = controller.command(pose, path, goal)
            candidate = pose.moved(command.linear, command.yaw_rate, control_dt_s)
            if active_world.collides(candidate, 0.20):
                candidate = pose.moved(0.0, 0.9, control_dt_s)
                path = []
                controller.reset()

            if policy_locomotion is None:
                pose = candidate
                _set_freejoint_pose(mujoco, model, data, pose, spec.base_height)
                if should_render:
                    _set_dynamic_obstacle_positions(mujoco, model, data, dynamic_obstacles, frame_time)
                    mujoco.mj_forward(model, data)
            else:
                policy_locomotion.step(data, command)
                for _ in range(_physics_substeps(model.opt.timestep, control_dt_s)):
                    mujoco.mj_step(model, data)
                pose = _read_freejoint_pose(mujoco, model, data, fallback=pose)

            if should_render:
                _write_renderer_frame(renderer, data, camera, scene_option, process)
                frame_count += 1
    except BrokenPipeError as exc:
        stderr = _close_ffmpeg_writer(process)
        renderer.close()
        renderer_closed = True
        raise RuntimeError(f"ffmpeg stopped while writing {output_path}: {_tail(stderr)}") from exc
    finally:
        if not renderer_closed:
            renderer.close()

    stderr = _close_ffmpeg_writer(process)
    if process.returncode != 0:
        raise RuntimeError(f"ffmpeg failed for {output_path}: {_tail(stderr)}")
    if not output_path.exists() or output_path.stat().st_size <= 0:
        raise RuntimeError(f"video export did not create a playable file: {output_path}")
    return MujocoVideoRecord(
        output_path=output_path,
        frame_count=frame_count,
        control_dt_s=control_dt_s,
        duration_s=steps * control_dt_s,
    )


def _robot_spec(robot: str) -> RobotSpec:
    try:
        return ROBOT_SPECS[robot]
    except KeyError as exc:
        supported = ", ".join(sorted(ROBOT_SPECS))
        raise ValueError(f"Unsupported robot: {robot}. Options: {supported}") from exc


def _resolve_model_path(
    spec: RobotSpec,
    model_path: str | Path | None,
    world: World2D,
    dynamic_obstacles: tuple[DynamicObstacle, ...],
) -> Path:
    if model_path is not None:
        return Path(model_path)
    if spec.name == "official_g1":
        return _ensure_official_g1_nav_scene(spec.default_model_path, world, dynamic_obstacles)
    if spec.name == "official_go2":
        return _ensure_official_go2_nav_scene(spec.default_model_path, world, dynamic_obstacles)
    return spec.default_model_path


def _ensure_official_g1_nav_scene(
    scene_path: Path,
    world: World2D,
    dynamic_obstacles: tuple[DynamicObstacle, ...],
) -> Path:
    robot_xml = scene_path.parent / "g1_29dof.xml"
    meshes_dir = scene_path.parent / "meshes"
    if not robot_xml.exists() or not meshes_dir.exists():
        robojudo_scene = _ensure_robojudo_g1_nav_scene(world, dynamic_obstacles)
        if robojudo_scene is not None:
            return robojudo_scene
        raise FileNotFoundError(
            "Could not find the official Unitree G1 model. Clone it with:\n"
            "mkdir -p g1_slam/third_party\n"
            "git clone --depth 1 --filter=blob:none --sparse "
            "https://github.com/unitreerobotics/unitree_mujoco.git g1_slam/third_party/unitree_mujoco\n"
            "cd g1_slam/third_party/unitree_mujoco\n"
            "git sparse-checkout set unitree_robots/g1"
        )
    scene_path.write_text(_official_g1_scene_xml(world, dynamic_obstacles), encoding="utf-8")
    return scene_path


def _ensure_robojudo_g1_nav_scene(
    world: World2D,
    dynamic_obstacles: tuple[DynamicObstacle, ...],
) -> Path | None:
    robojudo_g1_dir = G1_SLAM_ROOT / "third_party" / "RoboJuDo" / "assets" / "robots" / "g1"
    robot_xml = robojudo_g1_dir / "g1_29dof_rev_1_0.xml"
    meshes_dir = robojudo_g1_dir / "meshes"
    if not robot_xml.exists() or not meshes_dir.exists():
        return None
    scene_path = robojudo_g1_dir / "g1_nav_generated.xml"
    scene_path.write_text(
        _official_unitree_nav_scene_xml(
            world,
            model_name="g1_robojudo_nav",
            include_file=robot_xml.name,
            statistic_center="0 0 0.8",
            statistic_extent=8.0,
            dynamic_obstacles=dynamic_obstacles,
        ),
        encoding="utf-8",
    )
    return scene_path


def _official_g1_scene_xml(
    world: World2D,
    dynamic_obstacles: tuple[DynamicObstacle, ...] = (),
) -> str:
    return _official_unitree_nav_scene_xml(
        world,
        model_name="g1_official_nav",
        include_file="g1_29dof.xml",
        statistic_center="0 0 0.8",
        statistic_extent=8.0,
        dynamic_obstacles=dynamic_obstacles,
    )


def _ensure_official_go2_nav_scene(
    scene_path: Path,
    world: World2D,
    dynamic_obstacles: tuple[DynamicObstacle, ...],
) -> Path:
    robot_xml = scene_path.parent / "go2.xml"
    assets_dir = scene_path.parent / "assets"
    if not robot_xml.exists() or not assets_dir.exists():
        raise FileNotFoundError(
            "Could not find the official Unitree Go2 model. Clone it with:\n"
            "mkdir -p g1_slam/third_party\n"
            "git clone --depth 1 --filter=blob:none --sparse "
            "https://github.com/unitreerobotics/unitree_mujoco.git g1_slam/third_party/unitree_mujoco\n"
            "cd g1_slam/third_party/unitree_mujoco\n"
            "git sparse-checkout set unitree_robots/go2"
        )
    scene_path.write_text(_official_go2_scene_xml(world, dynamic_obstacles), encoding="utf-8")
    return scene_path


def _official_go2_scene_xml(
    world: World2D,
    dynamic_obstacles: tuple[DynamicObstacle, ...] = (),
) -> str:
    return _official_unitree_nav_scene_xml(
        world,
        model_name="go2_official_nav",
        include_file="go2.xml",
        statistic_center="0 0 0.35",
        statistic_extent=6.0,
        dynamic_obstacles=dynamic_obstacles,
    )


def _official_unitree_nav_scene_xml(
    world: World2D,
    *,
    model_name: str,
    include_file: str,
    statistic_center: str,
    statistic_extent: float,
    dynamic_obstacles: tuple[DynamicObstacle, ...],
) -> str:
    assets = navigation_scene_assets()
    environment = environment_scene_geoms(world)
    lighting = navigation_lights_and_camera()
    obstacles = "\n".join(
        static_obstacle_geom(index, obstacle) for index, obstacle in enumerate(world.obstacles)
    )
    dynamic_obstacle_bodies = "\n".join(
        dynamic_obstacle_scene_body(obstacle) for obstacle in dynamic_obstacles
    )
    visual_settings = navigation_visual_settings()
    return f"""<mujoco model="{model_name}">
  <include file="{include_file}"/>

  <statistic center="{statistic_center}" extent="{statistic_extent:.1f}"/>
{visual_settings}

  <asset>
{assets}
  </asset>

  <worldbody>
{lighting}
{environment}
    <geom name="goal" type="cylinder" pos="0 0 0.02" size="0.28 0.02" material="nav_goal_mat"/>
{obstacles}
{dynamic_obstacle_bodies}
  </worldbody>
</mujoco>
"""


def _set_dynamic_obstacle_positions(
    mujoco,
    model,
    data,
    obstacles: tuple[DynamicObstacle, ...],
    sim_time: float,
) -> None:
    for obstacle in obstacles:
        body_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, obstacle.name)
        if body_id < 0:
            continue
        mocap_id = int(model.body_mocapid[body_id])
        if mocap_id < 0:
            continue
        x, y = obstacle.xy_at(sim_time)
        data.mocap_pos[mocap_id][0] = x
        data.mocap_pos[mocap_id][1] = y
        data.mocap_pos[mocap_id][2] = 0.0 if obstacle.mode == "npc" else obstacle.half_height
        data.mocap_quat[mocap_id] = _yaw_quat(obstacle.yaw_at(sim_time))


def _world_with_dynamic_obstacles(
    world: World2D,
    obstacles: tuple[DynamicObstacle, ...],
    sim_time: float,
) -> World2D:
    if not obstacles:
        return world
    return World2D(
        x_min=world.x_min,
        y_min=world.y_min,
        x_max=world.x_max,
        y_max=world.y_max,
        obstacles=world.obstacles + tuple(obstacle.rect_at(sim_time) for obstacle in obstacles),
    )


def _yaw_quat(yaw: float) -> tuple[float, float, float, float]:
    half_yaw = 0.5 * yaw
    return (cos(half_yaw), 0.0, 0.0, sin(half_yaw))


def _set_home_keyframe_pose(mujoco, model, data) -> None:
    home_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "home")
    if home_id >= 0:
        mujoco.mj_resetDataKeyframe(model, data, home_id)


def _set_freejoint_pose(mujoco, model, data, pose: Pose2D, base_height: float) -> None:
    qpos_address = _first_freejoint_qpos_address(mujoco, model)
    if qpos_address is None:
        return
    half_yaw = 0.5 * pose.yaw
    data.qpos[qpos_address + 0] = pose.x
    data.qpos[qpos_address + 1] = pose.y
    data.qpos[qpos_address + 2] = base_height
    data.qpos[qpos_address + 3] = cos(half_yaw)
    data.qpos[qpos_address + 4] = 0.0
    data.qpos[qpos_address + 5] = 0.0
    data.qpos[qpos_address + 6] = sin(half_yaw)


def _first_freejoint_qpos_address(mujoco, model) -> int | None:
    for joint_id in range(model.njnt):
        if model.jnt_type[joint_id] == mujoco.mjtJoint.mjJNT_FREE:
            return int(model.jnt_qposadr[joint_id])
    return None


def _read_freejoint_pose(mujoco, model, data, fallback: Pose2D) -> Pose2D:
    qpos_address = _first_freejoint_qpos_address(mujoco, model)
    if qpos_address is None:
        return fallback
    qx = float(data.qpos[qpos_address + 3])
    qz = float(data.qpos[qpos_address + 6])
    yaw = 2.0 * _atan2(qz, qx)
    return Pose2D(float(data.qpos[qpos_address]), float(data.qpos[qpos_address + 1]), yaw)


def _atan2(y: float, x: float) -> float:
    from math import atan2

    return atan2(y, x)


def _set_goal_marker(mujoco, model, data, goal: tuple[float, float]) -> None:
    geom_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "goal")
    if geom_id < 0:
        return
    model.geom_pos[geom_id][0] = goal[0]
    model.geom_pos[geom_id][1] = goal[1]
    mujoco.mj_forward(model, data)


class _null_context:
    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return False


def _viewer(model, data):
    import mujoco.viewer

    return mujoco.viewer.launch_passive(model, data, show_left_ui=False, show_right_ui=False)


def _configure_viewer_camera(viewer, config: VisualizationConfig | None) -> None:
    if config is None:
        return
    if config.fixed_camera:
        try:
            import mujoco
        except ModuleNotFoundError:
            mujoco = None
        if mujoco is not None:
            viewer.cam.type = mujoco.mjtCamera.mjCAMERA_FREE
    if config.camera_lookat is not None:
        viewer.cam.lookat[:] = config.camera_lookat
    if config.camera_distance is not None:
        viewer.cam.distance = config.camera_distance
    if config.camera_azimuth is not None:
        viewer.cam.azimuth = config.camera_azimuth
    if config.camera_elevation is not None:
        viewer.cam.elevation = config.camera_elevation


def _offscreen_camera(mujoco, model, config: VisualizationConfig | None):
    camera = mujoco.MjvCamera()
    mujoco.mjv_defaultFreeCamera(model, camera)
    if config is None:
        return camera
    if config.fixed_camera:
        camera.type = mujoco.mjtCamera.mjCAMERA_FREE
    if config.camera_lookat is not None:
        camera.lookat[:] = config.camera_lookat
    if config.camera_distance is not None:
        camera.distance = config.camera_distance
    if config.camera_azimuth is not None:
        camera.azimuth = config.camera_azimuth
    if config.camera_elevation is not None:
        camera.elevation = config.camera_elevation
    return camera


def _offscreen_scene_option(mujoco):
    option = mujoco.MjvOption()
    option.geomgroup[5] = 0
    return option


def _suppress_robot_collision_visuals(
    mujoco,
    model,
    dynamic_obstacles: tuple[DynamicObstacle, ...],
) -> None:
    dynamic_body_names = {obstacle.name for obstacle in dynamic_obstacles}
    for geom_id in range(model.ngeom):
        if int(model.geom_group[geom_id]) != 0:
            continue
        body_id = int(model.geom_bodyid[geom_id])
        if body_id == 0:
            continue
        body_name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, body_id) or ""
        if body_name in dynamic_body_names:
            continue
        model.geom_group[geom_id] = 5


def _write_renderer_frame(renderer, data, camera, scene_option, process: subprocess.Popen) -> None:
    if process.stdin is None:
        raise RuntimeError("ffmpeg stdin is not available")
    renderer.update_scene(data, camera=camera, scene_option=scene_option)
    frame = renderer.render()
    process.stdin.write(frame.tobytes())


def _physics_substeps(physics_dt_s: float, control_dt_s: float) -> int:
    if physics_dt_s <= 0.0:
        return 1
    return max(1, round(control_dt_s / physics_dt_s))


def _render_stride(
    *,
    steps: int,
    fps: int,
    control_dt_s: float,
    max_duration_s: float | None,
) -> int:
    from math import ceil

    target_frame_dt_s = 1.0 / fps
    natural_stride = max(1, round(target_frame_dt_s / control_dt_s))
    if max_duration_s is None:
        return natural_stride
    max_frames = max(1, round(fps * max_duration_s))
    return max(natural_stride, ceil(max(steps, 1) / max_frames))


def _open_ffmpeg_writer(output_path: Path, *, fps: int, width: int, height: int) -> subprocess.Popen:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("ffmpeg is required to record MuJoCo survey videos")
    if not _ffmpeg_has_encoder(ffmpeg, "libx264"):
        raise RuntimeError("ffmpeg must include the libx264 encoder to write browser-compatible MP4")
    command = (
        ffmpeg,
        "-y",
        "-f",
        "rawvideo",
        "-vcodec",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{width}x{height}",
        "-framerate",
        str(fps),
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "18",
        "-r",
        str(fps),
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output_path),
    )
    return subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _ffmpeg_has_encoder(ffmpeg: str, encoder: str) -> bool:
    result = subprocess.run(
        (ffmpeg, "-hide_banner", "-encoders"),
        check=False,
        capture_output=True,
    )
    output = result.stdout.decode("utf-8", errors="replace")
    return result.returncode == 0 and encoder in output


def _close_ffmpeg_writer(process: subprocess.Popen) -> bytes:
    if process.stdin is not None and not process.stdin.closed:
        process.stdin.close()
    stderr = process.stderr.read() if process.stderr is not None else b""
    if process.stdout is not None:
        process.stdout.close()
    process.wait()
    if isinstance(stderr, str):
        return stderr.encode("utf-8", errors="replace")
    return stderr or b""


def _tail(value: bytes, limit: int = 800) -> str:
    return value.decode("utf-8", errors="replace")[-limit:]


def _ensure_offscreen_gl_backend() -> None:
    if os.environ.get("MUJOCO_GL"):
        return
    os.environ["MUJOCO_GL"] = "egl"

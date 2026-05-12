from __future__ import annotations

from dataclasses import dataclass
from math import cos, sin
from pathlib import Path
from time import sleep

from .config import LocomotionConfig, VisualizationConfig
from .controller import PurePursuitConfig
from .dynamic_obstacles import DynamicObstacle
from .geometry import Pose2D
from .simulation import make_grid_for_world
from .world import World2D


@dataclass(frozen=True)
class RobotSpec:
    name: str
    default_model_path: Path
    base_height: float
    use_physics_step: bool


ROBOT_SPECS = {
    "kinematic": RobotSpec(
        name="kinematic",
        default_model_path=Path("assets/g1_kinematic.xml"),
        base_height=0.72,
        use_physics_step=True,
    ),
    "official_g1": RobotSpec(
        name="official_g1",
        default_model_path=Path("third_party/unitree_mujoco/unitree_robots/g1/g1_nav_generated.xml"),
        base_height=0.80,
        use_physics_step=False,
    ),
    "official_go2": RobotSpec(
        name="official_go2",
        default_model_path=Path("third_party/unitree_mujoco/unitree_robots/go2/go2_nav_generated.xml"),
        base_height=0.27,
        use_physics_step=False,
    ),
}


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
) -> None:
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
                sleep(dt)


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
        raise FileNotFoundError(
            "Could not find the official Unitree G1 model. Clone it with:\n"
            "mkdir -p third_party\n"
            "git clone --depth 1 --filter=blob:none --sparse "
            "https://github.com/unitreerobotics/unitree_mujoco.git third_party/unitree_mujoco\n"
            "cd third_party/unitree_mujoco\n"
            "git sparse-checkout set unitree_robots/g1"
        )
    scene_path.write_text(_official_g1_scene_xml(world, dynamic_obstacles), encoding="utf-8")
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
            "mkdir -p third_party\n"
            "git clone --depth 1 --filter=blob:none --sparse "
            "https://github.com/unitreerobotics/unitree_mujoco.git third_party/unitree_mujoco\n"
            "cd third_party/unitree_mujoco\n"
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
    obstacle_geoms = []
    for index, obstacle in enumerate(world.obstacles):
        center_x = 0.5 * (obstacle.x_min + obstacle.x_max)
        center_y = 0.5 * (obstacle.y_min + obstacle.y_max)
        size_x = 0.5 * (obstacle.x_max - obstacle.x_min)
        size_y = 0.5 * (obstacle.y_max - obstacle.y_min)
        obstacle_geoms.append(
            f'    <geom name="obs_{index}" type="box" pos="{center_x:.4f} {center_y:.4f} 0.35" '
            f'size="{size_x:.4f} {size_y:.4f} 0.35" material="nav_obstacle_mat"/>'
        )

    floor_size_x = 0.5 * (world.x_max - world.x_min) + 1.0
    floor_size_y = 0.5 * (world.y_max - world.y_min) + 1.0
    floor_center_x = 0.5 * (world.x_min + world.x_max)
    floor_center_y = 0.5 * (world.y_min + world.y_max)
    obstacles = "\n".join(obstacle_geoms)
    dynamic_obstacle_bodies = "\n".join(
        _dynamic_obstacle_scene_body(obstacle) for obstacle in dynamic_obstacles
    )
    return f"""<mujoco model="{model_name}">
  <include file="{include_file}"/>

  <statistic center="{statistic_center}" extent="{statistic_extent:.1f}"/>
  <visual>
    <global azimuth="130" elevation="-35"/>
    <headlight ambient="0.55 0.55 0.55" diffuse="0.35 0.35 0.35" specular="0.03 0.03 0.03"/>
  </visual>

  <asset>
    <texture name="nav_grid" type="2d" builtin="checker" rgb1="0.18 0.19 0.20" rgb2="0.24 0.25 0.26" width="512" height="512"/>
    <material name="nav_floor_mat" texture="nav_grid" texrepeat="4 4" reflectance="0.1"/>
    <material name="nav_obstacle_mat" rgba="0.8 0.18 0.12 1"/>
    <material name="nav_dynamic_cylinder_mat" rgba="0.05 0.35 1.0 1"/>
    <material name="nav_npc_clothes_mat" rgba="0.16 0.32 0.44 1"/>
    <material name="nav_npc_skin_mat" rgba="0.78 0.58 0.42 1"/>
    <material name="nav_npc_leg_mat" rgba="0.08 0.08 0.09 1"/>
    <material name="nav_goal_mat" rgba="0.1 0.8 0.35 1"/>
  </asset>

  <worldbody>
    <light name="soft_top_light" directional="true" pos="0 0 8" dir="0 0 -1" ambient="0.35 0.35 0.35" diffuse="0.45 0.45 0.45" specular="0.02 0.02 0.02"/>
    <light name="soft_front_light" directional="true" pos="0 -5 6" dir="0 0.45 -1" ambient="0.18 0.18 0.18" diffuse="0.28 0.28 0.28" specular="0.01 0.01 0.01"/>
    <camera name="nav_overview" pos="1 -8 7" xyaxes="1 0 0 0 0.65 0.76"/>
    <geom name="floor" type="plane" pos="{floor_center_x:.4f} {floor_center_y:.4f} 0" size="{floor_size_x:.4f} {floor_size_y:.4f} 0.05" material="nav_floor_mat"/>
    <geom name="goal" type="cylinder" pos="0 0 0.02" size="0.28 0.02" material="nav_goal_mat"/>
{obstacles}
{dynamic_obstacle_bodies}
  </worldbody>
</mujoco>
"""


def _dynamic_obstacle_scene_body(obstacle: DynamicObstacle) -> str:
    x, y = obstacle.center
    if obstacle.mode == "npc":
        return (
            f'    <body name="{obstacle.name}" mocap="true" '
            f'pos="{x:.4f} {y:.4f} 0.0000">\n'
            f'      <geom name="{obstacle.name}_torso" type="capsule" '
            'fromto="0 0 0.72 0 0 1.32" size="0.16" '
            'material="nav_npc_clothes_mat"/>\n'
            f'      <geom name="{obstacle.name}_head" type="sphere" '
            'pos="0 0 1.55" size="0.14" material="nav_npc_skin_mat"/>\n'
            f'      <geom name="{obstacle.name}_left_leg" type="capsule" '
            'fromto="0 0.075 0.05 0 0.075 0.72" size="0.055" '
            'material="nav_npc_leg_mat"/>\n'
            f'      <geom name="{obstacle.name}_right_leg" type="capsule" '
            'fromto="0 -0.075 0.05 0 -0.075 0.72" size="0.055" '
            'material="nav_npc_leg_mat"/>\n'
            f'      <geom name="{obstacle.name}_personal_space" type="cylinder" '
            f'pos="0 0 0.01" size="{obstacle.radius:.4f} 0.01" '
            'rgba="0.16 0.32 0.44 0.16" contype="0" conaffinity="0"/>\n'
            "    </body>"
        )
    return (
        f'    <body name="{obstacle.name}" mocap="true" '
        f'pos="{x:.4f} {y:.4f} {obstacle.half_height:.4f}">\n'
        f'      <geom name="{obstacle.name}_geom" type="cylinder" '
        f'size="{obstacle.radius:.4f} {obstacle.half_height:.4f}" '
        'material="nav_dynamic_cylinder_mat"/>\n'
        "    </body>"
    )


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

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from math import atan2, cos, sin
from pathlib import Path

from .controller import PurePursuitConfig, PurePursuitController, VelocityCommand
from .dynamic_obstacles import DynamicCylinder, make_default_dynamic_cylinders
from .geometry import Pose2D, clamp, distance_xy
from .lidar import simulate_lidar
from .planner import AStarPlanner
from .simulation import make_grid_for_world
from .world import World2D


@dataclass(frozen=True)
class RoboJuDoBackendConfig:
    repo_path: Path = Path("third_party/RoboJuDo")
    config_name: str = "g1_asap_loco"
    max_vx: float = 0.5
    max_vy: float = 0.5
    max_yaw_rate: float = 1.0
    auto_start_walking: bool = True
    run_fullspeed: bool | None = None
    use_navigation_scene: bool = True
    enable_dynamic_cylinders: bool = False
    dynamic_cylinder_seed: int = 7


@dataclass(frozen=True)
class RoboJuDoCommand:
    vx: float = 0.0
    vy: float = 0.0
    yaw_rate: float = 0.0

    @classmethod
    def from_velocity_command(cls, command: VelocityCommand) -> RoboJuDoCommand:
        return cls(vx=command.linear, vy=0.0, yaw_rate=command.yaw_rate)


@dataclass
class _VirtualJoystickState:
    command: RoboJuDoCommand
    max_vx: float
    max_vy: float
    max_yaw_rate: float


_JOYSTICK_STATE = _VirtualJoystickState(
    command=RoboJuDoCommand(),
    max_vx=0.5,
    max_vy=0.5,
    max_yaw_rate=1.0,
)


class RoboJuDoBackend:
    """MuJoCo-only RoboJuDo locomotion backend.

    RoboJuDo policies already know how to read joystick-shaped command data.
    This backend replaces RoboJuDo's hardware joystick controller with a virtual
    controller fed by our SLAM/navigation velocity commands.
    """

    def __init__(self, config: RoboJuDoBackendConfig | None = None) -> None:
        self.config = config or RoboJuDoBackendConfig()
        self.config = replace(self.config, repo_path=self._install_repo_path(self.config.repo_path))
        self._install_virtual_joystick_controller(self.config)
        self.pipeline = self._build_pipeline(self.config)

    def set_command(self, command: VelocityCommand | RoboJuDoCommand) -> None:
        if isinstance(command, VelocityCommand):
            command = RoboJuDoCommand.from_velocity_command(command)
        _JOYSTICK_STATE.command = command

    def step(self, command: VelocityCommand | RoboJuDoCommand | None = None) -> Pose2D:
        if command is not None:
            self.set_command(command)
        self.pipeline.step()
        return self.pose()

    def pose(self) -> Pose2D:
        env = self.pipeline.env
        base_pos = getattr(env, "base_pos", None)
        base_quat = getattr(env, "base_quat", None)
        if base_pos is None or base_quat is None:
            return Pose2D(0.0, 0.0, 0.0)
        return Pose2D(float(base_pos[0]), float(base_pos[1]), _yaw_from_xyzw_quat(base_quat))

    def reset(self) -> None:
        self.pipeline.reset()

    def reborn(self, pose: Pose2D, base_height: float = 0.793) -> None:
        env = self.pipeline.env
        if not hasattr(env, "reborn"):
            return
        half_yaw = 0.5 * pose.yaw
        env.reborn(
            init_qpos=[
                pose.x,
                pose.y,
                base_height,
                cos(half_yaw),
                0.0,
                0.0,
                sin(half_yaw),
            ]
        )

    def set_goal_marker(self, goal: tuple[float, float]) -> None:
        env = self.pipeline.env
        if not hasattr(env, "model") or not hasattr(env, "data"):
            return
        try:
            import mujoco
        except ModuleNotFoundError:
            return
        geom_id = mujoco.mj_name2id(env.model, mujoco.mjtObj.mjOBJ_GEOM, "goal")
        if geom_id < 0:
            return
        env.model.geom_pos[geom_id][0] = goal[0]
        env.model.geom_pos[geom_id][1] = goal[1]
        mujoco.mj_forward(env.model, env.data)

    def set_dynamic_cylinders(
        self,
        cylinders: tuple[DynamicCylinder, ...],
        *,
        sim_time: float,
    ) -> None:
        if not cylinders:
            return
        env = self.pipeline.env
        if not hasattr(env, "model") or not hasattr(env, "data"):
            return
        try:
            import mujoco
        except ModuleNotFoundError:
            return
        for cylinder in cylinders:
            body_id = mujoco.mj_name2id(env.model, mujoco.mjtObj.mjOBJ_BODY, cylinder.name)
            if body_id < 0:
                continue
            mocap_id = int(env.model.body_mocapid[body_id])
            if mocap_id < 0:
                continue
            x, y = cylinder.xy_at(sim_time)
            env.data.mocap_pos[mocap_id, 0] = x
            env.data.mocap_pos[mocap_id, 1] = y
            env.data.mocap_pos[mocap_id, 2] = cylinder.half_height
            env.data.mocap_quat[mocap_id] = (1.0, 0.0, 0.0, 0.0)
        mujoco.mj_forward(env.model, env.data)

    def run_forever(self, command_provider: Callable[[], VelocityCommand | RoboJuDoCommand]) -> None:
        while True:
            start_time = time.time()
            self.step(command_provider())
            if not self.pipeline.cfg.run_fullspeed:
                sleep_s = self.pipeline.dt - (time.time() - start_time)
                if sleep_s > 0:
                    time.sleep(sleep_s)

    @staticmethod
    def _install_repo_path(repo_path: Path) -> Path:
        repo_path = _resolve_robojudo_repo_path(repo_path)
        if not repo_path.exists():
            raise FileNotFoundError(
                f"No se encontro RoboJuDo en {repo_path}. Clonalo con:\n"
                "mkdir -p third_party\n"
                "git clone -b release https://github.com/HansZ8/RoboJuDo.git third_party/RoboJuDo"
            )
        repo_path_text = repo_path.as_posix()
        if repo_path_text not in sys.path:
            sys.path.insert(0, repo_path_text)
        return repo_path

    @staticmethod
    def _install_virtual_joystick_controller(config: RoboJuDoBackendConfig) -> None:
        try:
            import robojudo.controller
            from robojudo.controller.base_ctrl import Controller
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "No pude importar RoboJuDo. Instala sus dependencias en tu entorno con "
                "`pip install -e third_party/RoboJuDo`."
            ) from exc

        _JOYSTICK_STATE.max_vx = config.max_vx
        _JOYSTICK_STATE.max_vy = config.max_vy
        _JOYSTICK_STATE.max_yaw_rate = config.max_yaw_rate

        @dataclass
        class VirtualJoystickCtrlCfg:
            ctrl_type: str = "JoystickCtrl"
            triggers: dict[str, str] | None = None
            triggers_extra: dict[str, str] | None = None
            auto_start_walking: bool = config.auto_start_walking

            def __post_init__(self) -> None:
                if self.triggers is None:
                    self.triggers = {}
                if self.triggers_extra is None:
                    self.triggers_extra = {}

        class VirtualJoystickCtrl(Controller):
            def __init__(self, cfg_ctrl: VirtualJoystickCtrlCfg, env=None, device: str = "cpu") -> None:
                super().__init__(cfg_ctrl=cfg_ctrl, env=env, device=device)
                self._emit_auto_start = cfg_ctrl.auto_start_walking

            def reset(self) -> None:
                self._emit_auto_start = self.cfg_ctrl.auto_start_walking

            def get_data(self) -> dict:
                command = _JOYSTICK_STATE.command
                axes = {
                    "LeftX": _axis(-command.vy, _JOYSTICK_STATE.max_vy),
                    "LeftY": _axis(command.vx, _JOYSTICK_STATE.max_vx),
                    "RightX": _axis(-command.yaw_rate, _JOYSTICK_STATE.max_yaw_rate),
                    "RightY": 0.0,
                }
                button_event = []
                if self._emit_auto_start:
                    button_event.append({"type": "button", "name": "Left", "pressed": True})
                    self._emit_auto_start = False
                return {"axes": axes, "button_event": button_event}

        robojudo.controller.JoystickCtrl = VirtualJoystickCtrl
        RoboJuDoBackend.VirtualJoystickCtrlCfg = VirtualJoystickCtrlCfg

    @staticmethod
    def _build_pipeline(config: RoboJuDoBackendConfig, world: World2D | None = None):
        import robojudo.pipeline
        from robojudo.config.config_manager import ConfigManager

        cfg = ConfigManager(config_name=config.config_name).get_cfg()
        cfg.ctrl = [RoboJuDoBackend.VirtualJoystickCtrlCfg()]
        if config.use_navigation_scene and world is not None:
            dynamic_cylinders = _dynamic_cylinders_from_config(config)
            cfg.env.xml = _ensure_robojudo_navigation_scene(
                config.repo_path,
                world,
                dynamic_cylinders,
            ).as_posix()
            if getattr(cfg.env, "forward_kinematic", None) is not None:
                cfg.env.forward_kinematic.xml_path = cfg.env.xml
        if config.run_fullspeed is not None:
            cfg.run_fullspeed = config.run_fullspeed

        pipeline_class = getattr(robojudo.pipeline, cfg.pipeline_type)
        return pipeline_class(cfg=cfg)


def run_robojudo_navigation(
    world: World2D,
    *,
    start: Pose2D,
    goal: tuple[float, float],
    steps: int,
    controller_config: PurePursuitConfig,
    backend_config: RoboJuDoBackendConfig | None = None,
) -> None:
    backend = RoboJuDoBackend.__new__(RoboJuDoBackend)
    backend.config = backend_config or RoboJuDoBackendConfig()
    backend.config = replace(backend.config, repo_path=backend._install_repo_path(backend.config.repo_path))
    backend._install_virtual_joystick_controller(backend.config)
    backend.pipeline = backend._build_pipeline(backend.config, world)
    backend.reset()
    backend.reborn(start)
    backend.set_goal_marker(goal)
    dynamic_cylinders = _dynamic_cylinders_from_config(backend.config)
    backend.set_dynamic_cylinders(dynamic_cylinders, sim_time=0.0)

    pose = backend.pose()
    if pose.x == 0.0 and pose.y == 0.0:
        pose = start

    grid = make_grid_for_world(world)
    planner = AStarPlanner(grid)
    controller = PurePursuitController(controller_config)
    path: list[tuple[float, float]] = []
    dt = float(getattr(backend.pipeline, "dt", 0.02))

    for step in range(steps):
        sim_time = step * dt
        backend.set_dynamic_cylinders(dynamic_cylinders, sim_time=sim_time)
        scan_world = _world_with_dynamic_cylinders(world, dynamic_cylinders, sim_time)
        scan = simulate_lidar(scan_world, pose)
        grid.update_from_scan(pose, scan)
        if step % 10 == 0 or not path or controller.waypoint_index >= len(path):
            path = planner.plan(pose, goal)
            controller.reset()

        command = controller.command(pose, path, goal)
        pose = backend.step(command)

        if distance_xy((pose.x, pose.y), goal) < controller.config.goal_tolerance:
            print(f"Meta alcanzada con RoboJuDo en {step + 1} pasos. Pose final: {pose}")
            return

    print(f"Meta no alcanzada con RoboJuDo en {steps} pasos. Pose final: {pose}")


def _axis(value: float, max_abs: float) -> float:
    if max_abs <= 0.0:
        return 0.0
    return clamp(value / max_abs, -1.0, 1.0)


def _resolve_robojudo_repo_path(repo_path: Path) -> Path:
    candidate = repo_path.resolve()
    if candidate.exists():
        return candidate
    package_root_candidate = Path(__file__).resolve().parents[2] / "third_party" / "RoboJuDo"
    if package_root_candidate.exists():
        return package_root_candidate
    return candidate


def _ensure_robojudo_navigation_scene(
    repo_path: Path,
    world: World2D,
    dynamic_cylinders: tuple[DynamicCylinder, ...] = (),
) -> Path:
    robot_dir = repo_path.resolve() / "assets" / "robots" / "g1"
    source_xml = robot_dir / "g1_29dof_rev_1_0.xml"
    scene_xml = robot_dir / "g1_29dof_nav.xml"
    if not source_xml.exists():
        raise FileNotFoundError(f"No se encontro el XML base de RoboJuDo: {source_xml}")

    source = source_xml.read_text(encoding="utf-8")
    marker = "  <!-- setup scene -->"
    marker_index = source.find(marker)
    if marker_index < 0:
        raise ValueError(f"No pude encontrar la seccion de escena en {source_xml}")
    scene_xml.write_text(
        source[:marker_index] + _robojudo_navigation_scene_tail(world, dynamic_cylinders),
        encoding="utf-8",
    )
    return scene_xml


def _robojudo_navigation_scene_tail(
    world: World2D,
    dynamic_cylinders: tuple[DynamicCylinder, ...],
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
    dynamic_cylinder_geoms = "\n".join(
        _dynamic_cylinder_scene_body(cylinder) for cylinder in dynamic_cylinders
    )
    return f"""  <!-- setup navigation scene -->
  <statistic center="1.0 0.0 1.0" extent="8.0"/>
  <visual>
    <headlight ambient="0.55 0.55 0.55" diffuse="0.35 0.35 0.35" specular="0.03 0.03 0.03"/>
    <rgba haze="0.15 0.18 0.2 1"/>
    <global azimuth="130" elevation="-35"/>
  </visual>
  <asset>
    <texture name="nav_grid" type="2d" builtin="checker" rgb1="0.18 0.19 0.20" rgb2="0.24 0.25 0.26" width="512" height="512"/>
    <material name="nav_floor_mat" texture="nav_grid" texrepeat="4 4" reflectance="0.1"/>
    <material name="nav_obstacle_mat" rgba="0.8 0.18 0.12 1"/>
    <material name="nav_dynamic_cylinder_mat" rgba="0.05 0.35 1.0 1"/>
    <material name="nav_goal_mat" rgba="0.1 0.8 0.35 1"/>
  </asset>
  <worldbody>
    <light name="soft_top_light" directional="true" pos="0 0 8" dir="0 0 -1" ambient="0.35 0.35 0.35" diffuse="0.45 0.45 0.45" specular="0.02 0.02 0.02"/>
    <light name="soft_front_light" directional="true" pos="0 -5 6" dir="0 0.45 -1" ambient="0.18 0.18 0.18" diffuse="0.28 0.28 0.28" specular="0.01 0.01 0.01"/>
    <camera name="nav_overview" pos="1 -8 7" xyaxes="1 0 0 0 0.65 0.76"/>
    <geom name="floor" type="plane" pos="{floor_center_x:.4f} {floor_center_y:.4f} 0" size="{floor_size_x:.4f} {floor_size_y:.4f} 0.05" material="nav_floor_mat"/>
    <geom name="goal" type="cylinder" pos="0 0 0.02" size="0.28 0.02" material="nav_goal_mat"/>
{obstacles}
{dynamic_cylinder_geoms}
  </worldbody>
</mujoco>
"""


def _dynamic_cylinder_scene_body(cylinder: DynamicCylinder) -> str:
    x, y = cylinder.center
    return (
        f'    <body name="{cylinder.name}" mocap="true" '
        f'pos="{x:.4f} {y:.4f} {cylinder.half_height:.4f}">\n'
        f'      <geom name="{cylinder.name}_geom" type="cylinder" '
        f'size="{cylinder.radius:.4f} {cylinder.half_height:.4f}" '
        'material="nav_dynamic_cylinder_mat"/>\n'
        "    </body>"
    )


def _dynamic_cylinders_from_config(config: RoboJuDoBackendConfig) -> tuple[DynamicCylinder, ...]:
    if not config.enable_dynamic_cylinders:
        return ()
    return make_default_dynamic_cylinders(config.dynamic_cylinder_seed)


def _world_with_dynamic_cylinders(
    world: World2D,
    cylinders: tuple[DynamicCylinder, ...],
    sim_time: float,
) -> World2D:
    if not cylinders:
        return world
    return World2D(
        x_min=world.x_min,
        y_min=world.y_min,
        x_max=world.x_max,
        y_max=world.y_max,
        obstacles=world.obstacles + tuple(cylinder.rect_at(sim_time) for cylinder in cylinders),
    )


def _yaw_from_xyzw_quat(quat) -> float:
    x = float(quat[0])
    y = float(quat[1])
    z = float(quat[2])
    w = float(quat[3])
    return atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


RoboJuDoBackend.VirtualJoystickCtrlCfg = None

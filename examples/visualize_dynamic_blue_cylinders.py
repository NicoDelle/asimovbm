from __future__ import annotations

import argparse
import time
from pathlib import Path

from g1_slam.dynamic_obstacles import DynamicCylinder, make_default_dynamic_cylinders

DEFAULT_MODEL = Path(
    "g1_slam/third_party/unitree_mujoco/unitree_robots/g1/"
    "scene_29dof_dynamic_blue_cylinders.xml"
)
DEFAULT_ROBOT_START_XY = (-6.0, 0.0)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Open a MuJoCo scene with dynamic blue cylinders that move in "
            "slow cyclic patterns."
        )
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=DEFAULT_MODEL,
        help=f"Path to the G1 dynamic-cylinder MuJoCo XML. Default: {DEFAULT_MODEL}",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=7,
        help="Seed used for deterministic random phases. Default: 7",
    )
    parser.add_argument(
        "--realtime",
        type=float,
        default=1.0,
        help="Wall-clock playback multiplier. 1.0 matches simulated time.",
    )
    parser.add_argument(
        "--robot-x",
        type=float,
        default=DEFAULT_ROBOT_START_XY[0],
        help=f"Initial G1 floating-base X position. Default: {DEFAULT_ROBOT_START_XY[0]}",
    )
    parser.add_argument(
        "--robot-y",
        type=float,
        default=DEFAULT_ROBOT_START_XY[1],
        help=f"Initial G1 floating-base Y position. Default: {DEFAULT_ROBOT_START_XY[1]}",
    )
    parser.add_argument(
        "--step-physics",
        action="store_true",
        help=(
            "Advance full MuJoCo physics. Without a controller the G1 may fall; "
            "the default mode keeps the robot pose stable for scene inspection."
        ),
    )
    args = parser.parse_args()
    run_viewer(
        model_path=args.model,
        seed=args.seed,
        realtime=args.realtime,
        robot_start_xy=(args.robot_x, args.robot_y),
        step_physics=args.step_physics,
    )


def run_viewer(
    *,
    model_path: Path,
    seed: int,
    realtime: float,
    robot_start_xy: tuple[float, float],
    step_physics: bool,
) -> None:
    try:
        import mujoco
        import mujoco.viewer
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "MuJoCo visualization requires the optional dependency: "
            "pip install -e '.[g1-mujoco]'"
        ) from exc

    model = mujoco.MjModel.from_xml_path(str(model_path))
    data = mujoco.MjData(model)
    _set_robot_start_pose(mujoco, model, data, robot_start_xy)
    motions = make_default_dynamic_cylinders(seed)
    mocap_ids = {
        motion.name: _mocap_id(mujoco, model, motion.name)
        for motion in motions
    }
    dt = float(model.opt.timestep)

    with mujoco.viewer.launch_passive(model, data) as viewer:
        while viewer.is_running():
            _apply_cylinder_motions(data, motions, mocap_ids, data.time)
            if step_physics:
                mujoco.mj_step(model, data)
            else:
                mujoco.mj_forward(model, data)
                data.time += dt
            viewer.sync()
            if realtime > 0:
                time.sleep(dt / realtime)


def _apply_cylinder_motions(
    data,
    motions: tuple[DynamicCylinder, ...],
    mocap_ids: dict[str, int],
    sim_time: float,
) -> None:
    for motion in motions:
        x, y = motion.xy_at(sim_time)
        mocap_id = mocap_ids[motion.name]
        data.mocap_pos[mocap_id, 0] = x
        data.mocap_pos[mocap_id, 1] = y
        data.mocap_pos[mocap_id, 2] = motion.half_height
        data.mocap_quat[mocap_id] = (1.0, 0.0, 0.0, 0.0)


def _mocap_id(mujoco, model, body_name: str) -> int:
    body_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, body_name)
    if body_id < 0:
        raise ValueError(f"Missing body in MuJoCo model: {body_name}")
    mocap_id = int(model.body_mocapid[body_id])
    if mocap_id < 0:
        raise ValueError(f"Body is not configured as a mocap body: {body_name}")
    return mocap_id


def _set_robot_start_pose(
    mujoco,
    model,
    data,
    robot_start_xy: tuple[float, float],
) -> None:
    qpos_address = _freejoint_qpos_address(mujoco, model, "floating_base_joint")
    data.qpos[qpos_address + 0] = robot_start_xy[0]
    data.qpos[qpos_address + 1] = robot_start_xy[1]


def _freejoint_qpos_address(mujoco, model, joint_name: str) -> int:
    joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, joint_name)
    if joint_id < 0:
        raise ValueError(f"Missing joint in MuJoCo model: {joint_name}")
    return int(model.jnt_qposadr[joint_id])


if __name__ == "__main__":
    main()

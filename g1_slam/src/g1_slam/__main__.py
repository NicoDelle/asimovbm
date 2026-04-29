from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_navigation_config
from .geometry import Pose2D
from .mujoco_runner import run_mujoco_navigation
from .simulation import run_navigation, save_trajectory
from .world import default_world


def main() -> None:
    parser = argparse.ArgumentParser(description="SLAM y navegacion para un humanoide tipo Unitree G1.")
    parser.add_argument("--config", type=Path, default=Path("config/navigation.json"))
    parser.add_argument("--steps", type=int)
    parser.add_argument("--start", nargs=3, type=float, metavar=("X", "Y", "YAW"))
    parser.add_argument("--goal", nargs=2, type=float, metavar=("X", "Y"))
    parser.add_argument("--out", type=Path, default=Path("runs"))
    parser.add_argument("--mujoco", action="store_true", help="usa MuJoCo como visualizacion")
    parser.add_argument("--robot", choices=("kinematic", "official_g1"), default="kinematic")
    parser.add_argument("--locomotion", choices=("kinematic", "policy"), help="sobrescribe locomotion.mode del config")
    parser.add_argument("--policy-path", type=Path, help="sobrescribe locomotion.policy_path del config")
    parser.add_argument("--model-path", type=Path, help="ruta opcional a un XML/MJCF de MuJoCo")
    parser.add_argument("--render", action="store_true", help="abre el viewer de MuJoCo")
    args = parser.parse_args()

    world = default_world()
    nav_config = load_navigation_config(args.config)
    start = Pose2D(*args.start) if args.start is not None else nav_config.start
    goal = (args.goal[0], args.goal[1]) if args.goal is not None else nav_config.goal
    steps = args.steps if args.steps is not None else nav_config.steps
    locomotion_config = nav_config.locomotion
    if args.locomotion is not None:
        locomotion_config = locomotion_config.__class__(
            mode=args.locomotion,
            policy_path=locomotion_config.policy_path,
            observation_size=locomotion_config.observation_size,
            action_scale=locomotion_config.action_scale,
            kp=locomotion_config.kp,
            kd=locomotion_config.kd,
        )
    if args.policy_path is not None:
        locomotion_config = locomotion_config.__class__(
            mode=locomotion_config.mode,
            policy_path=args.policy_path,
            observation_size=locomotion_config.observation_size,
            action_scale=locomotion_config.action_scale,
            kp=locomotion_config.kp,
            kd=locomotion_config.kd,
        )

    if args.mujoco:
        run_mujoco_navigation(
            world,
            robot=args.robot,
            model_path=args.model_path,
            start=start,
            goal=goal,
            steps=steps,
            controller_config=nav_config.controller,
            locomotion_config=locomotion_config,
            render=args.render,
        )
        return

    result = run_navigation(world, start=start, goal=goal, steps=steps, controller_config=nav_config.controller)
    args.out.mkdir(parents=True, exist_ok=True)
    result.grid.save_pgm(args.out / "map.pgm")
    save_trajectory(args.out / "path.csv", result.trajectory)
    status = "alcanzada" if result.reached_goal else "no alcanzada"
    print(f"Meta {status} en {result.steps} pasos. Pose final: {result.pose}")
    print(f"Mapa: {args.out / 'map.pgm'}")
    print(f"Trayectoria: {args.out / 'path.csv'}")


if __name__ == "__main__":
    main()

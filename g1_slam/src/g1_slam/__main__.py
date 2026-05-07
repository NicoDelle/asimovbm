from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_navigation_config
from .dynamic_obstacles import (
    DYNAMIC_SCENARIO_GOAL,
    DYNAMIC_SCENARIO_START,
    DYNAMIC_SCENARIO_STEPS,
    make_dynamic_cylinder_world,
)
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
    parser.add_argument("--locomotion", choices=("kinematic", "policy", "robojudo"), help="sobrescribe locomotion.mode del config")
    parser.add_argument("--policy-path", type=Path, help="sobrescribe locomotion.policy_path del config")
    parser.add_argument("--model-path", type=Path, help="ruta opcional a un XML/MJCF de MuJoCo")
    parser.add_argument("--robojudo-repo", type=Path, default=Path("third_party/RoboJuDo"))
    parser.add_argument("--robojudo-config", default="g1_asap_loco")
    parser.add_argument(
        "--dynamic-blue-cylinders",
        action="store_true",
        help="enable slow cyclic blue cylinders in the RoboJuDo SLAM scene",
    )
    parser.add_argument(
        "--dynamic-cylinder-seed",
        type=int,
        default=7,
        help="seed used for deterministic dynamic-cylinder phases",
    )
    parser.add_argument("--render", action="store_true", help="abre el viewer de MuJoCo")
    args = parser.parse_args()

    nav_config = load_navigation_config(args.config)
    if args.dynamic_blue_cylinders:
        world = make_dynamic_cylinder_world()
        default_start = DYNAMIC_SCENARIO_START
        default_goal = DYNAMIC_SCENARIO_GOAL
        default_steps = max(nav_config.steps, DYNAMIC_SCENARIO_STEPS)
    else:
        world = default_world()
        default_start = nav_config.start
        default_goal = nav_config.goal
        default_steps = nav_config.steps
    start = Pose2D(*args.start) if args.start is not None else default_start
    goal = (args.goal[0], args.goal[1]) if args.goal is not None else default_goal
    steps = args.steps if args.steps is not None else default_steps
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

    if locomotion_config.mode == "robojudo":
        from .robojudo_backend import RoboJuDoBackendConfig, run_robojudo_navigation

        run_robojudo_navigation(
            world,
            start=start,
            goal=goal,
            steps=steps,
            controller_config=nav_config.controller,
            backend_config=RoboJuDoBackendConfig(
                repo_path=args.robojudo_repo,
                config_name=args.robojudo_config,
                max_vx=nav_config.controller.max_linear_speed,
                max_vy=nav_config.controller.max_linear_speed,
                max_yaw_rate=nav_config.controller.max_yaw_rate,
                enable_dynamic_cylinders=args.dynamic_blue_cylinders,
                dynamic_cylinder_seed=args.dynamic_cylinder_seed,
            ),
        )
        return

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

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .config import LocomotionConfig, load_navigation_config
from .dynamic_obstacles import (
    DYNAMIC_SCENARIO_GOAL,
    DYNAMIC_SCENARIO_START,
    DYNAMIC_SCENARIO_STEPS,
    make_default_dynamic_cylinders,
    make_dynamic_cylinder_world,
)
from .geometry import Pose2D
from .mujoco_runner import run_mujoco_navigation
from .simulation import run_navigation, save_trajectory
from .world import default_world

DEFAULT_GO2_POLICY_PATH = Path("policies/go2/unitree_rl_mjlab/policy.onnx")


def main() -> None:
    parser = argparse.ArgumentParser(description="SLAM and navigation for Unitree robots in MuJoCo.")
    parser.add_argument("--config", type=Path, default=Path("config/navigation.json"))
    parser.add_argument("--steps", type=int)
    parser.add_argument("--start", nargs=3, type=float, metavar=("X", "Y", "YAW"))
    parser.add_argument("--goal", nargs=2, type=float, metavar=("X", "Y"))
    parser.add_argument("--out", type=Path, default=Path("runs"))
    parser.add_argument("--mujoco", action="store_true", help="use MuJoCo for visualization")
    parser.add_argument("--robot", choices=("kinematic", "official_g1", "official_go2"), default="kinematic")
    parser.add_argument("--locomotion", choices=("kinematic", "policy", "robojudo"), help="override config locomotion.mode")
    parser.add_argument("--policy-path", type=Path, help="override config locomotion.policy_path")
    parser.add_argument("--model-path", type=Path, help="optional path to a MuJoCo XML/MJCF file")
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
        default=None,
        help="seed used for deterministic dynamic-cylinder phases",
    )
    parser.add_argument("--render", action="store_true", help="open the MuJoCo viewer")
    args = parser.parse_args()

    nav_config = load_navigation_config(args.config)
    enable_dynamic_cylinders = (
        nav_config.dynamic_obstacles.blue_cylinders or args.dynamic_blue_cylinders
    )
    dynamic_cylinder_seed = (
        args.dynamic_cylinder_seed
        if args.dynamic_cylinder_seed is not None
        else nav_config.dynamic_obstacles.blue_cylinder_seed
    )
    dynamic_cylinders = ()
    if enable_dynamic_cylinders:
        dynamic_cylinders = make_default_dynamic_cylinders(dynamic_cylinder_seed)
        if nav_config.dynamic_obstacles.blue_cylinder_count is not None:
            dynamic_cylinders = dynamic_cylinders[
                : max(0, nav_config.dynamic_obstacles.blue_cylinder_count)
            ]
    if nav_config.world is not None:
        world = nav_config.world
        default_start = nav_config.start
        default_goal = nav_config.goal
        default_steps = nav_config.steps
    elif enable_dynamic_cylinders:
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
            observation_profile=locomotion_config.observation_profile,
            action_scale=locomotion_config.action_scale,
            kp=locomotion_config.kp,
            kd=locomotion_config.kd,
        )
    if args.policy_path is not None:
        locomotion_config = locomotion_config.__class__(
            mode=locomotion_config.mode,
            policy_path=args.policy_path,
            observation_size=locomotion_config.observation_size,
            observation_profile=locomotion_config.observation_profile,
            action_scale=locomotion_config.action_scale,
            kp=locomotion_config.kp,
            kd=locomotion_config.kd,
        )
    locomotion_config = _fallback_missing_default_go2_policy(
        locomotion_config,
        robot=args.robot,
        explicit_policy_path=args.policy_path is not None,
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
                enable_dynamic_cylinders=enable_dynamic_cylinders,
                dynamic_cylinder_seed=dynamic_cylinder_seed,
                dynamic_cylinder_count=nav_config.dynamic_obstacles.blue_cylinder_count,
                visualization=nav_config.visualization,
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
            visualization_config=nav_config.visualization,
            render=args.render,
            dynamic_cylinders=dynamic_cylinders,
        )
        return

    result = run_navigation(world, start=start, goal=goal, steps=steps, controller_config=nav_config.controller)
    args.out.mkdir(parents=True, exist_ok=True)
    result.grid.save_pgm(args.out / "map.pgm")
    save_trajectory(args.out / "path.csv", result.trajectory)
    status = "reached" if result.reached_goal else "not reached"
    print(f"Goal {status} in {result.steps} steps. Final pose: {result.pose}")
    print(f"Map: {args.out / 'map.pgm'}")
    print(f"Trajectory: {args.out / 'path.csv'}")


def _fallback_missing_default_go2_policy(
    locomotion_config: LocomotionConfig,
    *,
    robot: str,
    explicit_policy_path: bool,
) -> LocomotionConfig:
    policy_path = locomotion_config.policy_path
    if (
        robot != "official_go2"
        or locomotion_config.mode != "policy"
        or explicit_policy_path
        or policy_path != DEFAULT_GO2_POLICY_PATH
        or policy_path.exists()
    ):
        return locomotion_config

    print(
        "Warning: the default Go2 ONNX policy was not found at "
        f"{policy_path}. Falling back to kinematic MuJoCo locomotion for this "
        "run. Provide --policy-path with a real Go2 velocity policy to use "
        "dynamic policy locomotion.",
        file=sys.stderr,
    )
    return LocomotionConfig(
        mode="kinematic",
        policy_path=policy_path,
        observation_size=locomotion_config.observation_size,
        observation_profile=locomotion_config.observation_profile,
        action_scale=locomotion_config.action_scale,
        kp=locomotion_config.kp,
        kd=locomotion_config.kd,
    )


if __name__ == "__main__":
    main()

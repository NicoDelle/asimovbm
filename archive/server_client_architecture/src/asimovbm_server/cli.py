"""``asimovbm-server`` CLI entry point."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .simulation.fake import fake_step

logger = logging.getLogger("asimovbm.server")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="asimovbm-server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--bootstrap-token",
        default=None,
        help="Admin/bootstrap token. If omitted, a fresh random token is generated and printed.",
    )
    parser.add_argument(
        "--artifact-root",
        type=Path,
        default=Path("./artifacts"),
        help="Directory for per-run artifact output.",
    )
    parser.add_argument(
        "--disable-loopback-bootstrap",
        action="store_true",
        help="Require the bootstrap token even from 127.0.0.1.",
    )
    parser.add_argument(
        "--orchestrator",
        choices=("scripted", "mujoco", "echo", "local-validation"),
        default="scripted",
        help="Control-loop orchestrator to run. 'mujoco' loads the package XML and steps it.",
    )
    parser.add_argument(
        "--episode-pack",
        type=Path,
        default=Path("examples/episode_packs/social_navigation_mvp.json"),
        help="Episode pack for local-validation mode.",
    )
    parser.add_argument(
        "--robot-profile",
        default="minimal-mobile-base",
        help="Robot profile for local-validation mode.",
    )
    parser.add_argument(
        "--agent-profile",
        default="reference-social-nav",
        help="Agent policy for local-validation mode.",
    )
    parser.add_argument(
        "--visible",
        action="store_true",
        help="Open a MuJoCo viewer when the selected robot adapter exposes one.",
    )
    parser.add_argument(
        "--demo-steps",
        type=int,
        default=5,
        help="Number of fake simulation steps to stream in scripted mode.",
    )
    parser.add_argument(
        "--step-delay-s",
        type=float,
        default=0.0,
        help="Delay before each streamed step in scripted mode, useful for watching the loop.",
    )
    parser.add_argument(
        "--package-root",
        type=Path,
        default=Path("examples/robot_packages/minimal"),
        help="Local package root used by the MuJoCo orchestrator to resolve model.path.",
    )
    parser.add_argument(
        "--mujoco-steps",
        type=int,
        default=20,
        help="Maximum MuJoCo control steps before terminal report.",
    )
    parser.add_argument(
        "--mujoco-control-dt",
        type=float,
        default=0.05,
        help="MuJoCo control timestep used by the mobile-base smoke adapter.",
    )
    parser.add_argument(
        "--trace-messages",
        action="store_true",
        help="Print each WebSocket envelope and simulation step in scripted mode.",
    )
    parser.add_argument("--log-level", default="info")
    return parser


def _redacted_log_value(token: str) -> str:
    if len(token) <= 8:
        return "<redacted>"
    return f"{token[:4]}...{token[-4:]}"


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=args.log_level.upper())

    if args.orchestrator == "local-validation":
        from asimovbm_server.benchmarks import (
            BenchmarkRunConfig,
            EpisodicValidationRunner,
            write_result_json,
        )
        from asimovbm_server.episodes import load_episode_pack

        args.artifact_root.mkdir(parents=True, exist_ok=True)
        pack = load_episode_pack(args.episode_pack)
        result = EpisodicValidationRunner().run(
            pack,
            BenchmarkRunConfig(
                robot_profile_id=args.robot_profile,
                agent_id=args.agent_profile,
                visible=args.visible,
            ),
        )
        output_path = args.artifact_root / f"{pack.id}-validation-result.json"
        write_result_json(result, output_path)
        logger.info(
            "Local validation complete: attempts=%s valid_episodes=%s result=%s",
            result.attempts,
            result.valid_episodes,
            output_path,
        )
        return 0

    import uvicorn
    from .app import create_app
    from .config import ServerConfig
    from .sessions import SessionManager

    bootstrap_token = args.bootstrap_token
    if not bootstrap_token:
        config = ServerConfig.from_env(artifact_root=args.artifact_root)
        bootstrap_token = config.bootstrap_token
        logger.warning(
            "Bootstrap token not provided. Generated one (redacted=%s). "
            "Use --bootstrap-token to supply your own.",
            _redacted_log_value(bootstrap_token),
        )

    config = ServerConfig(
        bootstrap_token=bootstrap_token,
        artifact_root=args.artifact_root,
        allow_loopback_session_creation=not args.disable_loopback_bootstrap,
    )
    args.artifact_root.mkdir(parents=True, exist_ok=True)
    if args.orchestrator == "echo":
        app = create_app(config)
    elif args.orchestrator == "scripted":
        from asimovbm_protocol import TerminalStatus
        from asimovbm_server.runner import ScriptedLifecycleOrchestrator

        manager = SessionManager(config)
        steps = [
            fake_step(step_id, sim_time=(step_id - 1) * 0.025)
            for step_id in range(1, args.demo_steps + 1)
        ]
        delays = {
            step.step_id: args.step_delay_s for step in steps if args.step_delay_s > 0
        }
        orchestrator = ScriptedLifecycleOrchestrator(
            manager,
            steps,
            terminal_status=TerminalStatus.REPORT_READY,
            delay_before_step_id=delays,
            trace_messages=args.trace_messages,
        )
        app = create_app(config, session_manager=manager, orchestrator=orchestrator)
        logger.info(
            "Scripted benchmark server ready: demo_steps=%s trace_messages=%s",
            args.demo_steps,
            args.trace_messages,
        )
    else:
        from asimovbm_server.runner import MuJoCoLifecycleOrchestrator

        manager = SessionManager(config)
        orchestrator = MuJoCoLifecycleOrchestrator(
            manager,
            package_root=args.package_root,
            max_steps=args.mujoco_steps,
            control_dt=args.mujoco_control_dt,
            trace_messages=args.trace_messages,
        )
        app = create_app(config, session_manager=manager, orchestrator=orchestrator)
        logger.info(
            "MuJoCo benchmark server ready: package_root=%s max_steps=%s trace_messages=%s",
            args.package_root,
            args.mujoco_steps,
            args.trace_messages,
        )

    uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

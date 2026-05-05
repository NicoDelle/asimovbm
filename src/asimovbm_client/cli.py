from __future__ import annotations

import argparse
import sys
from pathlib import Path

from asimovbm_client.protocol import (
    SensorReading,
    StepMessage,
    TaskEvent,
    TerminalStatus,
)
from asimovbm_client.robot_package import PackageLoadError, load_robot_package
from asimovbm_client.runner import (
    ParticipantCodeError,
    RunnerConfig,
    StepSynchronousRunner,
    load_callable,
)
from asimovbm_client.telemetry import summarize_failures
from asimovbm_client.testing import FakeBenchmarkServer, FakeServerScript


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="asimovbm-client")
    parser.add_argument(
        "--server",
        default="fake://local",
        help="fake://local, http(s)://host:port, or ws(s)://host:port",
    )
    parser.add_argument("--run-token", help="Pre-issued run token. Required for real servers when --bootstrap-token is not used.")
    parser.add_argument("--run-id", help="Pre-issued run id (paired with --run-token).")
    parser.add_argument(
        "--bootstrap-token",
        help="Admin token used to create a fresh session through the server's bootstrap route.",
    )
    parser.add_argument("--participant-id", help="Participant id for diagnostics")
    parser.add_argument("--robot-package", required=True, help="Path to robot package directory")
    parser.add_argument("--transformer", required=True, help="Python reference module:callable")
    parser.add_argument("--policy", required=True, help="Python reference module:callable")
    parser.add_argument("--diagnostics", action="store_true", help="Print local diagnostic details")
    parser.add_argument(
        "--receive-timeout-s",
        type=float,
        default=10.0,
        help="Per-message receive timeout (real transport only)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    is_real = args.server != "fake://local"
    if is_real and not args.run_token and not args.bootstrap_token:
        print(
            "Real server transport requires either --run-token or --bootstrap-token.",
            file=sys.stderr,
        )
        return 2
    if not is_real and not args.run_token:
        print("--run-token is required for the fake backend", file=sys.stderr)
        return 2

    try:
        package = load_robot_package(Path(args.robot_package))
        transformer = load_callable(args.transformer)
        policy = load_callable(args.policy)
    except (PackageLoadError, ParticipantCodeError) as exc:
        print(f"setup error: {exc}", file=sys.stderr)
        return 2

    action_size = len(package.action_mapping.get("joints", []))

    if is_real:
        from asimovbm_client.transport import (
            TransportConfig,
            WebSocketBenchmarkServer,
        )

        transport = WebSocketBenchmarkServer(
            TransportConfig(
                server_url=args.server,
                run_token=args.run_token,
                run_id=args.run_id,
                bootstrap_token=args.bootstrap_token,
                receive_timeout_s=args.receive_timeout_s,
            )
        )
        # The transport handles SessionBootstrap construction in connect();
        # we still feed it through the runner so participant_id flows.
        runner = StepSynchronousRunner(
            transport,
            package,
            transformer,
            policy,
            RunnerConfig(
                run_token=args.run_token or "<server-issued>",
                participant_id=args.participant_id,
                action_size=action_size,
            ),
        )
        try:
            # Run the package validation through the runner (it sees one
            # BenchmarkServer interface; the transport splits HTTP vs WS).
            result = runner.run()
        finally:
            transport.close()
    else:
        server = FakeBenchmarkServer(FakeServerScript(steps=[_sample_step()]))
        runner = StepSynchronousRunner(
            server,
            package,
            transformer,
            policy,
            RunnerConfig(
                run_token=args.run_token,
                participant_id=args.participant_id,
                action_size=action_size,
            ),
        )
        result = runner.run()

    if args.diagnostics:
        for line in summarize_failures(result.failures):
            print(line)
    if result.terminal is None:
        print("client run failed before terminal state", file=sys.stderr)
        return 1
    if result.terminal.status not in {TerminalStatus.COMPLETED, TerminalStatus.REPORT_READY}:
        print(f"client run ended with {result.terminal.status.value}", file=sys.stderr)
        return 1
    print(f"completed {result.steps_completed} step(s); report={result.terminal.report_ref}")
    return 0


def _sample_step() -> StepMessage:
    return StepMessage(
        step_id=1,
        sim_time=0.0,
        control_dt=0.025,
        sensors=[
            SensorReading("proprioception", "robot_state", {"joint_positions": [0.0, 0.0]}),
            SensorReading("lidar_front", "lidar", {"ranges": [1.5, 2.0, 1.2]}),
        ],
        task_events=[TaskEvent("come_here", {"target_id": "human_1"})],
    )


if __name__ == "__main__":
    raise SystemExit(main())

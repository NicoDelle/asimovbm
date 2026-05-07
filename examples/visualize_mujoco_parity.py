from __future__ import annotations

import argparse
import time
from collections.abc import Iterable
from pathlib import Path

from asimovbm_protocol import ActionMessage
from asimovbm_server.simulation import MuJoCoAdapterConfig, MuJoCoSimulationAdapter

DEFAULT_MODEL = Path("examples/robot_packages/minimal/robot.xml")
DEFAULT_SCENARIO = "arc"
SCENARIOS: dict[str, list[tuple[float, float]]] = {
    "straight": [(0.4, 0.0)] * 40,
    "turn": [(0.0, 0.6)] * 50,
    "arc": [(0.35, 0.4)] * 60,
    "mixed": (
        [(0.4, 0.0)] * 25
        + [(0.0, 0.6)] * 25
        + [(0.35, 0.4)] * 45
        + [(0.0, 0.0)] * 10
    ),
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Open a MuJoCo viewer for the server-owned mobile-base parity smoke path."
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=DEFAULT_MODEL,
        help=f"Path to the MuJoCo XML model. Default: {DEFAULT_MODEL}",
    )
    parser.add_argument(
        "--scenario",
        choices=sorted(SCENARIOS),
        default=DEFAULT_SCENARIO,
        help=f"Open-loop command scenario to play. Default: {DEFAULT_SCENARIO}",
    )
    parser.add_argument(
        "--dt",
        type=float,
        default=0.05,
        help="Control timestep in simulated seconds. Default: 0.05",
    )
    parser.add_argument(
        "--realtime",
        type=float,
        default=1.0,
        help="Wall-clock playback multiplier. 1.0 matches simulated time.",
    )
    args = parser.parse_args()

    run_viewer(
        model_path=args.model,
        commands=SCENARIOS[args.scenario],
        dt=args.dt,
        realtime=args.realtime,
    )


def run_viewer(
    *,
    model_path: Path,
    commands: Iterable[tuple[float, float]],
    dt: float,
    realtime: float,
) -> None:
    import mujoco.viewer

    commands = list(commands)
    adapter = MuJoCoSimulationAdapter(
        MuJoCoAdapterConfig(
            model_path=model_path,
            max_steps=len(commands),
            control_dt=dt,
            goal=(100.0, 100.0),
        )
    )

    with mujoco.viewer.launch_passive(adapter.model, adapter.data) as viewer:
        viewer.sync()
        for linear_velocity, yaw_rate in commands:
            if not viewer.is_running():
                break
            step = adapter.next_step()
            adapter.apply_action(
                ActionMessage(
                    step.step_id,
                    [linear_velocity, yaw_rate],
                    latency_ms=0.0,
                )
            )
            viewer.sync()
            if realtime > 0:
                time.sleep(dt / realtime)

        while viewer.is_running():
            viewer.sync()
            time.sleep(0.05)


if __name__ == "__main__":
    main()

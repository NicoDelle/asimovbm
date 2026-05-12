from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import pytest
from g1_slam.geometry import Pose2D

from asimovbm_protocol import ActionMessage
from asimovbm_server.simulation import (
    MuJoCoAdapterConfig,
    MuJoCoSimulationAdapter,
    SimulationStepError,
)

PACKAGE_ROOT = Path("examples/robot_packages/minimal")
POSITION_TOLERANCE_M = 0.01
YAW_TOLERANCE_RAD = 1e-6
TIME_TOLERANCE_S = 1e-9


@dataclass(frozen=True)
class PoseSample:
    step_id: int
    sim_time: float
    x: float
    y: float
    yaw: float


@dataclass(frozen=True)
class TraceDrift:
    final_position_error: float
    final_yaw_error: float
    max_position_error: float
    max_yaw_error: float
    first_divergent_step: int | None


def test_angle_distance_wraps_across_pi_boundary() -> None:
    assert _angle_distance(math.pi - 0.01, -math.pi + 0.01) == pytest.approx(0.02)


def test_trace_comparison_reports_first_divergent_step() -> None:
    reference = [
        PoseSample(1, 0.1, 0.0, 0.0, 0.0),
        PoseSample(2, 0.2, 1.0, 0.0, 0.0),
    ]
    candidate = [
        PoseSample(1, 0.1, 0.0, 0.0, 0.0),
        PoseSample(2, 0.2, 1.2, 0.0, 0.0),
    ]

    drift = _compare_traces(candidate, reference)

    assert drift.first_divergent_step == 2
    assert drift.max_position_error == pytest.approx(0.2)


@pytest.mark.parametrize(
    ("scenario_name", "commands"),
    [
        ("straight", [(0.4, 0.0), (0.4, 0.0), (0.4, 0.0)]),
        ("turn_in_place", [(0.0, 0.5), (0.0, 0.5), (0.0, -0.25)]),
        ("arc", [(0.35, 0.4), (0.35, 0.4), (0.35, 0.4), (0.35, -0.2)]),
    ],
)
def test_mujoco_and_g1_slam_match_open_loop_mobile_base_trace(
    scenario_name: str,
    commands: list[tuple[float, float]],
) -> None:
    _require_mujoco()
    dt = 0.05

    mujoco_trace = _run_mujoco_trace(commands, dt)
    g1_trace = _run_g1_slam_trace(commands, dt)

    drift = _compare_traces(mujoco_trace, g1_trace)
    assert drift.final_position_error <= POSITION_TOLERANCE_M, _format_drift(
        scenario_name, drift
    )
    assert drift.final_yaw_error <= YAW_TOLERANCE_RAD, _format_drift(scenario_name, drift)
    assert drift.max_position_error <= POSITION_TOLERANCE_M, _format_drift(
        scenario_name, drift
    )
    assert drift.max_yaw_error <= YAW_TOLERANCE_RAD, _format_drift(scenario_name, drift)


@pytest.mark.parametrize(
    ("invalid_action", "message"),
    [
        ([0.5], r"\[linear, yaw_rate\]"),
        ([math.nan, 0.0], "linear_velocity must be a finite number"),
        ([0.5, math.inf], "yaw_rate must be a finite number"),
    ],
)
def test_mujoco_trace_rejects_invalid_action_without_sample(
    invalid_action: list[float],
    message: str,
) -> None:
    _require_mujoco()
    adapter = _make_mujoco_adapter(max_steps=1)
    step = adapter.next_step()

    with pytest.raises(SimulationStepError, match=message):
        adapter.apply_action(ActionMessage(step.step_id, invalid_action, latency_ms=0.0))

    report = adapter.smoke_result()
    assert report.steps == 0
    assert report.trajectory_summary["points"] == 1


def _run_mujoco_trace(commands: Iterable[tuple[float, float]], dt: float) -> list[PoseSample]:
    commands = list(commands)
    adapter = _make_mujoco_adapter(max_steps=len(commands), dt=dt)
    samples: list[PoseSample] = []
    for command in commands:
        step = adapter.next_step()
        outcome = adapter.apply_action(
            ActionMessage(step.step_id, [command[0], command[1]], latency_ms=0.0)
        )
        pose = outcome["pose_after"]
        samples.append(
            PoseSample(
                step_id=step.step_id,
                sim_time=step.sim_time + step.control_dt,
                x=pose["x"],
                y=pose["y"],
                yaw=pose["yaw"],
            )
        )
    return samples


def _run_g1_slam_trace(commands: Iterable[tuple[float, float]], dt: float) -> list[PoseSample]:
    pose = Pose2D(0.0, 0.0, 0.0)
    samples: list[PoseSample] = []
    for index, (linear_velocity, yaw_rate) in enumerate(commands, start=1):
        pose = pose.moved(linear_velocity, yaw_rate, dt)
        samples.append(
            PoseSample(
                step_id=index,
                sim_time=index * dt,
                x=pose.x,
                y=pose.y,
                yaw=pose.yaw,
            )
        )
    return samples


def _make_mujoco_adapter(
    *,
    max_steps: int,
    dt: float = 0.05,
) -> MuJoCoSimulationAdapter:
    return MuJoCoSimulationAdapter(
        MuJoCoAdapterConfig(
            PACKAGE_ROOT / "robot.xml",
            max_steps=max_steps,
            control_dt=dt,
            goal=(100.0, 100.0),
        )
    )


def _require_mujoco() -> None:
    pytest.importorskip(
        "mujoco",
        reason="MuJoCo parity tests require the optional dependency: pip install -e '.[g1-mujoco]'",
    )


def _compare_traces(candidate: list[PoseSample], reference: list[PoseSample]) -> TraceDrift:
    assert len(candidate) == len(reference)
    max_position_error = 0.0
    max_yaw_error = 0.0
    first_divergent_step: int | None = None

    for candidate_sample, reference_sample in zip(candidate, reference, strict=True):
        assert candidate_sample.step_id == reference_sample.step_id
        assert candidate_sample.sim_time == pytest.approx(
            reference_sample.sim_time, abs=TIME_TOLERANCE_S
        )
        position_error = _position_error(candidate_sample, reference_sample)
        yaw_error = _angle_distance(candidate_sample.yaw, reference_sample.yaw)
        max_position_error = max(max_position_error, position_error)
        max_yaw_error = max(max_yaw_error, yaw_error)
        if (
            first_divergent_step is None
            and (position_error > POSITION_TOLERANCE_M or yaw_error > YAW_TOLERANCE_RAD)
        ):
            first_divergent_step = candidate_sample.step_id

    final_position_error = _position_error(candidate[-1], reference[-1]) if candidate else 0.0
    final_yaw_error = (
        _angle_distance(candidate[-1].yaw, reference[-1].yaw) if candidate else 0.0
    )
    return TraceDrift(
        final_position_error=final_position_error,
        final_yaw_error=final_yaw_error,
        max_position_error=max_position_error,
        max_yaw_error=max_yaw_error,
        first_divergent_step=first_divergent_step,
    )


def _position_error(candidate: PoseSample, reference: PoseSample) -> float:
    return math.hypot(candidate.x - reference.x, candidate.y - reference.y)


def _angle_distance(candidate: float, reference: float) -> float:
    return abs(math.atan2(math.sin(candidate - reference), math.cos(candidate - reference)))


def _format_drift(scenario_name: str, drift: TraceDrift) -> str:
    return (
        f"MuJoCo/G1 SLAM parity drift exceeded tolerance for {scenario_name}: "
        f"final_position_error={drift.final_position_error:.12g}, "
        f"final_yaw_error={drift.final_yaw_error:.12g}, "
        f"max_position_error={drift.max_position_error:.12g}, "
        f"max_yaw_error={drift.max_yaw_error:.12g}, "
        f"first_divergent_step={drift.first_divergent_step}"
    )

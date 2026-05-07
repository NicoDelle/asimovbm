"""MuJoCo-backed server simulation adapter.

The server owns this object: it loads the participant-submitted MJCF XML,
advances the simulation state after each accepted client action, and emits
protocol observations back over the benchmark control loop.
"""

from __future__ import annotations

import importlib
import importlib.util
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from asimovbm_protocol import ActionMessage, SensorReading, StepMessage, TaskEvent

from .base import SimulationSetupError, SimulationSmokeResult, SimulationStepError


@dataclass(frozen=True)
class _Pose2D:
    x: float
    y: float
    yaw: float


@dataclass(frozen=True)
class MuJoCoAdapterConfig:
    model_path: Path
    max_steps: int = 20
    control_dt: float = 0.05
    goal: tuple[float, float] = (1.0, 0.0)
    goal_tolerance: float = 0.05
    action_mapping: dict[str, Any] = field(default_factory=dict)


class MuJoCoSimulationAdapter:
    """Stepwise MuJoCo adapter for the benchmark server control loop."""

    maturity = "mujoco_mobile_base_smoke"

    def __init__(self, config: MuJoCoAdapterConfig) -> None:
        self.config = config
        self._mujoco = _import_mujoco()
        self._model_path = config.model_path.resolve()
        if not self._model_path.exists():
            raise SimulationSetupError(f"MuJoCo model path does not exist: {self._model_path}")

        try:
            self.model = self._mujoco.MjModel.from_xml_path(str(self._model_path))
            self.data = self._mujoco.MjData(self.model)
        except Exception as exc:
            raise SimulationSetupError(f"failed to load MuJoCo XML: {exc}") from exc

        self.model.opt.timestep = float(config.control_dt)
        self._freejoint_qpos_adr = self._find_freejoint_qpos_adr()
        self._step_id = 0
        self._awaiting_action_for: int | None = None
        self.actions: list[dict[str, Any]] = []
        self._trajectory: list[_Pose2D] = [self._pose()]
        self._mujoco.mj_forward(self.model, self.data)

    @property
    def terminal(self) -> bool:
        return self._step_id >= self.config.max_steps or self._distance_to_goal() <= self.config.goal_tolerance

    def next_step(self) -> StepMessage:
        if self.terminal:
            raise SimulationStepError("MuJoCo simulation is already terminal")
        if self._awaiting_action_for is not None:
            raise SimulationStepError(
                f"already waiting for action for step {self._awaiting_action_for}"
            )

        self._step_id += 1
        self._awaiting_action_for = self._step_id
        pose = self._pose()
        return StepMessage(
            step_id=self._step_id,
            sim_time=(self._step_id - 1) * self.config.control_dt,
            control_dt=self.config.control_dt,
            sensors=[
                SensorReading(
                    "pose",
                    "proprioception",
                    {
                        "x": pose.x,
                        "y": pose.y,
                        "yaw": pose.yaw,
                        "qpos": [float(value) for value in self.data.qpos],
                    },
                ),
                SensorReading(
                    "proprioception",
                    "robot_state",
                    {
                        "qpos": [float(value) for value in self.data.qpos],
                        "qvel": [float(value) for value in self.data.qvel],
                    },
                ),
                SensorReading(
                    "lidar_front",
                    "lidar",
                    {"ranges": [10.0] * 9, "max_range": 10.0},
                    units="m",
                ),
            ],
            task_events=[
                TaskEvent(
                    "come_here",
                    {
                        "goal": {"x": self.config.goal[0], "y": self.config.goal[1]},
                        "distance": self._distance_to_goal(),
                    },
                )
            ],
        )

    def apply_action(self, action: ActionMessage) -> dict[str, Any]:
        if self._awaiting_action_for is None:
            raise SimulationStepError("no MuJoCo step is awaiting an action")
        if action.step_id != self._awaiting_action_for:
            raise SimulationStepError(
                f"action step_id {action.step_id} does not match pending step {self._awaiting_action_for}"
            )
        if not action.valid:
            raise SimulationStepError(action.invalid_reason or "client marked action invalid")
        if len(action.action) != 2:
            raise SimulationStepError("MuJoCo mobile-base smoke actions require [linear, yaw_rate]")

        linear_velocity = _finite_float(action.action[0], "linear_velocity")
        yaw_rate = _finite_float(action.action[1], "yaw_rate")
        before = self._pose()
        dt = self.config.control_dt
        yaw = _wrap_angle(before.yaw + yaw_rate * dt)
        after = _Pose2D(
            x=before.x + linear_velocity * math.cos(yaw) * dt,
            y=before.y + linear_velocity * math.sin(yaw) * dt,
            yaw=yaw,
        )
        self._write_pose(after)
        self._mujoco.mj_forward(self.model, self.data)
        self._trajectory.append(after)
        outcome = {
            "step_id": action.step_id,
            "linear_velocity": linear_velocity,
            "yaw_rate": yaw_rate,
            "pose_before": _pose_to_dict(before),
            "pose_after": _pose_to_dict(after),
        }
        self.actions.append(outcome)
        self._awaiting_action_for = None
        return outcome

    def smoke_result(self) -> SimulationSmokeResult:
        final_pose = self._pose()
        return SimulationSmokeResult(
            maturity=self.maturity,
            reached_goal=self._distance_to_goal() <= self.config.goal_tolerance,
            steps=len(self.actions),
            final_pose=_pose_to_dict(final_pose),
            trajectory_summary=_summarize_pose_trajectory(self._trajectory),
            telemetry={
                "actions": list(self.actions),
                "goal": {"x": self.config.goal[0], "y": self.config.goal[1]},
                "model_path": str(self._model_path),
            },
        )

    def _find_freejoint_qpos_adr(self) -> int:
        freejoint_type = int(self._mujoco.mjtJoint.mjJNT_FREE)
        for joint_id in range(self.model.njnt):
            if int(self.model.jnt_type[joint_id]) == freejoint_type:
                return int(self.model.jnt_qposadr[joint_id])
        raise SimulationSetupError("MuJoCo smoke adapter requires a freejoint root body")

    def _pose(self) -> _Pose2D:
        adr = self._freejoint_qpos_adr
        qpos = self.data.qpos
        yaw = _yaw_from_quaternion(
            float(qpos[adr + 3]),
            float(qpos[adr + 4]),
            float(qpos[adr + 5]),
            float(qpos[adr + 6]),
        )
        return _Pose2D(float(qpos[adr]), float(qpos[adr + 1]), yaw)

    def _write_pose(self, pose: _Pose2D) -> None:
        adr = self._freejoint_qpos_adr
        qpos = self.data.qpos
        z = float(qpos[adr + 2])
        qpos[adr] = pose.x
        qpos[adr + 1] = pose.y
        qpos[adr + 2] = z
        qpos[adr + 3] = math.cos(pose.yaw / 2.0)
        qpos[adr + 4] = 0.0
        qpos[adr + 5] = 0.0
        qpos[adr + 6] = math.sin(pose.yaw / 2.0)
        self.data.qvel[:] = 0.0

    def _distance_to_goal(self) -> float:
        pose = self._pose()
        return math.hypot(self.config.goal[0] - pose.x, self.config.goal[1] - pose.y)


def mujoco_available() -> bool:
    return importlib.util.find_spec("mujoco") is not None


def _import_mujoco():
    try:
        return importlib.import_module("mujoco")
    except ModuleNotFoundError as exc:
        raise SimulationSetupError(
            "MuJoCo backend requires the optional dependency: pip install -e '.[g1-mujoco]'"
        ) from exc


def _finite_float(value: float, name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise SimulationStepError(f"{name} must be a finite number")
    return float(value)


def _wrap_angle(value: float) -> float:
    return math.atan2(math.sin(value), math.cos(value))


def _yaw_from_quaternion(w: float, x: float, y: float, z: float) -> float:
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    return math.atan2(siny_cosp, cosy_cosp)


def _pose_to_dict(pose: _Pose2D) -> dict[str, float]:
    return {"x": pose.x, "y": pose.y, "yaw": pose.yaw}


def _summarize_pose_trajectory(trajectory: list[_Pose2D]) -> dict[str, Any]:
    if not trajectory:
        return {"points": 0, "samples": []}
    return {
        "points": len(trajectory),
        "start": _pose_to_dict(trajectory[0]),
        "end": _pose_to_dict(trajectory[-1]),
        "samples": [
            {"step": index, **_pose_to_dict(pose)}
            for index, pose in enumerate(trajectory)
        ],
    }

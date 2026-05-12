"""Fake server-side simulation adapter for runner tests and protocol demos."""

from __future__ import annotations

from dataclasses import dataclass, field

from asimovbm_protocol import ActionMessage, SensorReading, StepMessage, TaskEvent

from .base import SimulationSmokeResult, SimulationStepError


def fake_step(step_id: int = 1, *, sim_time: float = 0.0) -> StepMessage:
    return StepMessage(
        step_id=step_id,
        sim_time=sim_time,
        control_dt=0.025,
        sensors=[
            SensorReading(
                "pose",
                "proprioception",
                {"x": 0.1 * (step_id - 1), "y": 0.0, "yaw": 0.0},
            )
        ],
        task_events=[TaskEvent("come_here", {"target_id": "fake-human"})],
    )


@dataclass
class FakeSmokeSimulation:
    steps: list[StepMessage] = field(default_factory=lambda: [fake_step()])

    def __post_init__(self) -> None:
        self.actions: list[ActionMessage] = []
        self._index = 0
        self._awaiting_step_id: int | None = None

    @property
    def terminal(self) -> bool:
        return self._index >= len(self.steps) and self._awaiting_step_id is None

    def next_step(self) -> StepMessage:
        if self._awaiting_step_id is not None:
            raise SimulationStepError(
                f"step {self._awaiting_step_id} still needs an action"
            )
        if self._index >= len(self.steps):
            raise SimulationStepError("fake simulation is already terminal")
        step = self.steps[self._index]
        self._index += 1
        self._awaiting_step_id = step.step_id
        return step

    def apply_action(self, action: ActionMessage) -> None:
        if self._awaiting_step_id is None:
            raise SimulationStepError("next_step() must be called before action")
        if action.step_id != self._awaiting_step_id:
            raise SimulationStepError(
                f"action step_id {action.step_id} does not match pending "
                f"step {self._awaiting_step_id}"
            )
        if not action.valid:
            raise SimulationStepError(action.invalid_reason or "invalid action")
        self.actions.append(action)
        self._awaiting_step_id = None

    def smoke_result(self) -> SimulationSmokeResult:
        last_step = self.steps[min(max(self._index - 1, 0), len(self.steps) - 1)]
        pose = next(sensor for sensor in last_step.sensors if sensor.name == "pose")
        return SimulationSmokeResult(
            maturity="fake_protocol",
            reached_goal=True,
            steps=len(self.actions),
            final_pose={
                "x": float(pose.data["x"]),
                "y": float(pose.data["y"]),
                "yaw": float(pose.data["yaw"]),
            },
            trajectory_summary={
                "points": len(self.actions) + 1,
                "start": {"x": 0.0, "y": 0.0, "yaw": 0.0},
                "end": {
                    "x": float(pose.data["x"]),
                    "y": float(pose.data["y"]),
                    "yaw": float(pose.data["yaw"]),
                },
            },
            telemetry={
                "actions": [
                    {"step_id": action.step_id, "action": list(action.action)}
                    for action in self.actions
                ]
            },
        )

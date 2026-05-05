"""Episode telemetry and technical diagnostics."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from math import isfinite
from typing import Any

from asimovbm_protocol import FailureCategory, FailureMessage, SensorReading, StepMessage
from asimovbm_server.simulation import SimulationSmokeResult


class TelemetryValidationError(RuntimeError):
    """Raised when adapter telemetry is not sufficient for reporting."""


@dataclass(frozen=True)
class TechnicalDiagnostic:
    category: FailureCategory
    summary: str
    attempt: int
    step_id: int | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_failure_message(self) -> FailureMessage:
        return FailureMessage(
            self.category,
            self.summary,
            step_id=self.step_id,
            details={"attempt": self.attempt, **self.details},
        )


def copy_smoke_result(result: SimulationSmokeResult) -> SimulationSmokeResult:
    """Deep-copy smoke telemetry before an adapter mutates again."""
    payload = deepcopy(result.to_report_context())
    return SimulationSmokeResult(
        maturity=payload["maturity"],
        reached_goal=payload["reached_goal"],
        steps=payload["steps"],
        final_pose=payload["final_pose"],
        trajectory_summary=payload["trajectory_summary"],
        telemetry=payload["telemetry"],
    )


def validate_step_telemetry(step: StepMessage) -> None:
    if not isfinite(step.sim_time) or step.sim_time < 0.0:
        raise TelemetryValidationError("step sim_time must be finite and non-negative")
    pose = _find_sensor(step.sensors, "pose")
    if pose is None:
        raise TelemetryValidationError("step is missing required pose sensor")
    if not isinstance(pose.data, dict):
        raise TelemetryValidationError("pose sensor data must be an object")
    for key in ("x", "y", "yaw"):
        value = pose.data.get(key)
        if not isinstance(value, (int, float)) or not isfinite(float(value)):
            raise TelemetryValidationError(f"pose.{key} must be a finite number")


def _find_sensor(sensors: list[SensorReading], name: str) -> SensorReading | None:
    for sensor in sensors:
        if sensor.name == name:
            return sensor
    return None

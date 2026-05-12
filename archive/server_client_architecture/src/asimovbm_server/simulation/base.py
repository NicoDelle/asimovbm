"""Shared simulation adapter primitives.

Adapters in this package convert concrete simulator output into small,
JSON-compatible smoke telemetry. Full benchmark episode accounting and metric
scoring are layered on top later; this module only describes what a smoke run
proved and what data it produced.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class SimulationSetupError(RuntimeError):
    """Raised when a simulation adapter cannot be configured."""


class SimulationStepError(RuntimeError):
    """Raised when a policy-in-loop step cannot be applied."""


@dataclass(frozen=True)
class SimulationSmokeResult:
    """Report-ready telemetry envelope for fake and real smoke runs."""

    maturity: str
    reached_goal: bool
    steps: int
    final_pose: dict[str, float]
    trajectory_summary: dict[str, Any]
    telemetry: dict[str, Any] = field(default_factory=dict)

    def to_report_context(self) -> dict[str, Any]:
        return {
            "maturity": self.maturity,
            "reached_goal": self.reached_goal,
            "steps": self.steps,
            "final_pose": dict(self.final_pose),
            "trajectory_summary": dict(self.trajectory_summary),
            "telemetry": dict(self.telemetry),
        }


def pose_to_dict(pose: Any) -> dict[str, float]:
    return {"x": float(pose.x), "y": float(pose.y), "yaw": float(pose.yaw)}


def summarize_trajectory(
    trajectory: tuple[Any, ...] | list[Any],
    *,
    max_samples: int = 12,
) -> dict[str, Any]:
    if not trajectory:
        return {"points": 0, "samples": []}
    stride = max(1, len(trajectory) // max_samples)
    samples = [
        {"step": index, **pose_to_dict(pose)}
        for index, pose in enumerate(trajectory)
        if index % stride == 0
    ]
    if samples[-1]["step"] != len(trajectory) - 1:
        samples.append({"step": len(trajectory) - 1, **pose_to_dict(trajectory[-1])})
    return {
        "points": len(trajectory),
        "start": pose_to_dict(trajectory[0]),
        "end": pose_to_dict(trajectory[-1]),
        "samples": samples,
    }

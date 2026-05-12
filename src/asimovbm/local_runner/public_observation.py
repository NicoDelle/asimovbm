"""Build policy-facing observations from an explicit public allowlist."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

FORBIDDEN_PUBLIC_KEYS: tuple[str, ...] = (
    "canonical_backend_id",
    "evaluator",
    "future_cue",
    "hidden",
    "measurement",
    "metadata",
    "metric",
    "proof",
    "provenance",
    "role",
    "source",
    "threshold",
)


def build_public_observation(
    *,
    robot_pose: tuple[float, float, float],
    goal: tuple[float, float],
    distance_to_goal: float,
    lidar_range_count: int,
    visible_entities: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    return {
        "robot_pose": robot_pose,
        "goal": goal,
        "distance_to_goal": distance_to_goal,
        "lidar_range_count": lidar_range_count,
        "visible_entities": tuple(_public_entity(entity) for entity in visible_entities),
    }


def public_observation_violations(value: Any) -> tuple[str, ...]:
    violations: list[str] = []
    _collect_violations(value, path="public_observation", violations=violations)
    return tuple(violations)


def _public_entity(entity: Mapping[str, Any]) -> dict[str, Any]:
    pose = entity.get("pose")
    payload: dict[str, Any] = {
        "id": entity.get("id"),
        "type": entity.get("type"),
        "shape": entity.get("shape"),
        "pose": pose,
        "radius": entity.get("radius"),
    }
    return {key: value for key, value in payload.items() if value is not None}


def _collect_violations(value: Any, *, path: str, violations: list[str]) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            if _is_forbidden_key(key_text):
                violations.append(f"{path}.{key_text}")
            _collect_violations(child, path=f"{path}.{key_text}", violations=violations)
    elif isinstance(value, (tuple, list)):
        for index, child in enumerate(value):
            _collect_violations(child, path=f"{path}[{index}]", violations=violations)


def _is_forbidden_key(key: str) -> bool:
    normalized = key.lower()
    return any(fragment in normalized for fragment in FORBIDDEN_PUBLIC_KEYS)

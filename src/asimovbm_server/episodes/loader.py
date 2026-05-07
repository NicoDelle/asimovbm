"""Episode pack loading and validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import (
    CueDefinition,
    EntityDefinition,
    EpisodeDefinition,
    EpisodePack,
    EpisodePackError,
    GoalDefinition,
    Pose2D,
    TierDefinition,
)

SUPPORTED_PACK_VERSION = 1


def load_episode_pack(path: Path) -> EpisodePack:
    data = _load_mapping(path)
    pack = episode_pack_from_mapping(data)
    validate_episode_pack(pack)
    return pack


def episode_pack_from_mapping(data: dict[str, Any]) -> EpisodePack:
    version = _required_int(data, "version")
    tiers = tuple(_tier_from_mapping(item) for item in _required_list(data, "tiers"))
    return EpisodePack(
        id=_required_str(data, "id"),
        version=version,
        tiers=tiers,
        metadata=dict(data.get("metadata", {})),
    )


def validate_episode_pack(pack: EpisodePack) -> None:
    if pack.version != SUPPORTED_PACK_VERSION:
        raise EpisodePackError(
            f"unsupported episode pack version {pack.version}; expected {SUPPORTED_PACK_VERSION}"
        )
    if not pack.tiers:
        raise EpisodePackError("episode pack must define at least one tier")

    tier_ids: set[str] = set()
    for tier in pack.tiers:
        if tier.id in tier_ids:
            raise EpisodePackError(f"duplicate tier id: {tier.id}")
        tier_ids.add(tier.id)
        if not tier.episodes:
            raise EpisodePackError(f"tier {tier.id} must define at least one episode")

        episode_ids: set[str] = set()
        for episode in tier.episodes:
            if episode.id in episode_ids:
                raise EpisodePackError(f"duplicate episode id in tier {tier.id}: {episode.id}")
            episode_ids.add(episode.id)
            _validate_episode(episode)


def _validate_episode(episode: EpisodeDefinition) -> None:
    entity_ids: set[str] = set()
    for entity in episode.entities:
        if entity.id in entity_ids:
            raise EpisodePackError(f"duplicate entity id in episode {episode.id}: {entity.id}")
        entity_ids.add(entity.id)
        if entity.radius <= 0:
            raise EpisodePackError(f"entity {entity.id} in episode {episode.id} needs radius > 0")

    for cue in episode.cues:
        if cue.source not in entity_ids:
            raise EpisodePackError(
                f"cue source {cue.source} in episode {episode.id} does not match an entity"
            )

    if episode.goal and episode.goal.target_human_id:
        human_ids = {human.id for human in episode.humans}
        if episode.goal.target_human_id not in human_ids:
            raise EpisodePackError(
                f"goal target {episode.goal.target_human_id} in episode {episode.id} "
                "does not match a human"
            )
    elif episode.goal is None:
        raise EpisodePackError(f"episode {episode.id} must define a goal")


def _tier_from_mapping(data: dict[str, Any]) -> TierDefinition:
    return TierDefinition(
        id=_required_str(data, "id"),
        episodes=tuple(_episode_from_mapping(item) for item in _required_list(data, "episodes")),
        required_valid_episodes=_optional_int(data, "required_valid_episodes"),
        max_attempts=_optional_int(data, "max_attempts"),
        metadata=dict(data.get("metadata", {})),
    )


def _episode_from_mapping(data: dict[str, Any]) -> EpisodeDefinition:
    return EpisodeDefinition(
        id=_required_str(data, "id"),
        scenario_type=_required_str(data, "scenario_type"),
        robot_start=_pose_from_mapping(_required_dict(data, "robot_start")),
        goal=_goal_from_mapping(_required_dict(data, "goal")),
        obstacles=tuple(
            _entity_from_mapping(item, kind="obstacle") for item in data.get("obstacles", [])
        ),
        humans=tuple(_entity_from_mapping(item, kind="human") for item in data.get("humans", [])),
        cues=tuple(_cue_from_mapping(item) for item in data.get("cues", [])),
        max_steps=int(data.get("max_steps", 200)),
        control_dt=float(data.get("control_dt", 0.05)),
        bounds=_bounds_from_mapping(data.get("bounds")),
        metadata=dict(data.get("metadata", {})),
    )


def _pose_from_mapping(data: dict[str, Any]) -> Pose2D:
    return Pose2D(float(data["x"]), float(data["y"]), float(data.get("yaw", 0.0)))


def _goal_from_mapping(data: dict[str, Any]) -> GoalDefinition:
    return GoalDefinition(
        x=_optional_float(data, "x"),
        y=_optional_float(data, "y"),
        target_human_id=data.get("target_human_id"),
        stop_distance_m=_optional_float(data, "stop_distance_m"),
    )


def _entity_from_mapping(data: dict[str, Any], *, kind: str) -> EntityDefinition:
    role = data.get("role")
    if role is None and kind == "human":
        role = "human"
    if role is None and kind == "obstacle":
        role = "obstacle"
    return EntityDefinition(
        id=_required_str(data, "id"),
        kind=kind,
        x=float(data["x"]),
        y=float(data["y"]),
        radius=float(data["radius"]),
        role=role,
        posture=data.get("posture"),
        public_before_cue=bool(data.get("public_before_cue", True)),
        metadata=dict(data.get("metadata", {})),
    )


def _cue_from_mapping(data: dict[str, Any]) -> CueDefinition:
    return CueDefinition(
        time_s=float(data["time_s"]),
        type=_required_str(data, "type"),
        source=_required_str(data, "source"),
        payload=dict(data.get("payload", {})),
    )


def _bounds_from_mapping(value: Any) -> tuple[float, float, float, float] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return (
            float(value["min_x"]),
            float(value["min_y"]),
            float(value["max_x"]),
            float(value["max_y"]),
        )
    if isinstance(value, list | tuple) and len(value) == 4:
        return tuple(float(item) for item in value)  # type: ignore[return-value]
    raise EpisodePackError("bounds must be a mapping or four-value list")


def _load_mapping(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise EpisodePackError(f"episode pack path does not exist: {path}")
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        try:
            import yaml  # type: ignore[import-not-found]
        except ModuleNotFoundError as exc:
            raise EpisodePackError(
                "YAML episode packs require PyYAML; use .json or install the server extras"
            ) from exc
        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise EpisodePackError("episode pack root must be a mapping")
    return data


def _required_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise EpisodePackError(f"missing required string field: {key}")
    return value


def _required_int(data: dict[str, Any], key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise EpisodePackError(f"missing required integer field: {key}")
    return value


def _optional_int(data: dict[str, Any], key: str) -> int | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise EpisodePackError(f"{key} must be an integer")
    return value


def _optional_float(data: dict[str, Any], key: str) -> float | None:
    value = data.get(key)
    if value is None:
        return None
    return float(value)


def _required_dict(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise EpisodePackError(f"missing required mapping field: {key}")
    return value


def _required_list(data: dict[str, Any], key: str) -> list[Any]:
    value = data.get(key)
    if not isinstance(value, list):
        raise EpisodePackError(f"missing required list field: {key}")
    return value

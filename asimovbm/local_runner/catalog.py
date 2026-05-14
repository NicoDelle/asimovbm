"""Catalog for the six canonical point-to-point `g1_slam` validation episodes.

The catalog is deliberately small and file-backed. Each entry points at one of
the checked-in JSON configs, stores a checksum of the exact bytes used for the
run, and preserves the parsed `g1_slam` navigation config for execution.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from g1_slam.config import LocomotionConfig, NavigationConfig, load_navigation_config

DEFAULT_EPISODE_IDS: tuple[str, ...] = (
    "g1_point_to_point_open",
    "g1_point_to_point_static_obstacles",
    "g1_point_to_point_dynamic_npcs",
    "go2_point_to_point_open",
    "go2_point_to_point_static_obstacles",
    "go2_point_to_point_dynamic_npcs",
)

ROBOT_IDS: tuple[str, ...] = ("g1", "go2")

DEFAULT_POLICY_BY_ROBOT: dict[str, str] = {
    "g1": "g1_robojudo_asap",
    "go2": "go2_unitree_rl_mjlab",
}

POLICY_PROFILES: dict[str, dict[str, Any]] = {
    "g1_robojudo_asap": {
        "robot_id": "g1",
        "locomotion": {
            "mode": "robojudo",
            "policy_path": Path("policies/g1/policy.onnx"),
            "robojudo_config": "g1_asap_loco",
            "observation_size": None,
            "observation_profile": "generic",
            "action_scale": 0.25,
            "kp": 35.0,
            "kd": 1.0,
        },
    },
    "g1_robojudo_unitree": {
        "robot_id": "g1",
        "locomotion": {
            "mode": "robojudo",
            "policy_path": Path("policies/g1/policy.onnx"),
            "robojudo_config": "g1",
            "observation_size": None,
            "observation_profile": "generic",
            "action_scale": 0.25,
            "kp": 35.0,
            "kd": 1.0,
        },
    },
    "go2_unitree_rl_mjlab": {
        "robot_id": "go2",
        "locomotion": {
            "mode": "policy",
            "policy_path": Path("policies/go2/unitree_rl_mjlab/policy.onnx"),
            "robojudo_config": "g1_asap_loco",
            "observation_size": 45,
            "observation_profile": "dias_ai_master_go2_velocity_flat",
            "action_scale": 0.5,
            "kp": 50.0,
            "kd": 3.5,
        },
    },
}

POLICY_IDS: tuple[str, ...] = tuple(POLICY_PROFILES)


class EpisodeCatalogError(RuntimeError):
    """Raised when the checked-in episode catalog is incomplete or ambiguous."""


@dataclass(frozen=True)
class LocalEpisodeSpec:
    """One canonical local validation episode."""

    id: str
    title: str
    description: str
    path: Path
    checksum_sha256: str
    raw_config: Mapping[str, Any]
    config: NavigationConfig
    robot_id: str
    policy_id: str
    robot_selector: str
    canonical_backend_id: str

    @property
    def steps(self) -> int:
        return self.config.steps

    @property
    def locomotion_mode(self) -> str:
        return self.config.locomotion.mode

    def to_manifest(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "path": self.path.as_posix(),
            "checksum_sha256": self.checksum_sha256,
            "steps": self.steps,
            "robot_id": self.robot_id,
            "policy_id": self.policy_id,
            "policy_path": self.config.locomotion.policy_path.as_posix()
            if self.config.locomotion.policy_path is not None
            else None,
            "robot_selector": self.robot_selector,
            "canonical_backend_id": self.canonical_backend_id,
            "locomotion_mode": self.locomotion_mode,
            "start": {
                "x": self.config.start.x,
                "y": self.config.start.y,
                "yaw": self.config.start.yaw,
            },
            "goal": {"x": self.config.goal[0], "y": self.config.goal[1]},
            "controller": {
                "start_delay_s": self.config.controller.start_delay_s,
            },
            "dynamic_obstacles": dict(self.raw_config.get("dynamic_obstacles", {})),
            "visualization": dict(self.raw_config.get("visualization", {})),
        }

    def with_policy(self, policy_id: str, policy_path: Path | None = None) -> LocalEpisodeSpec:
        profile = _policy_profile_for(self.robot_id, policy_id)
        profile_locomotion = dict(profile["locomotion"])
        if policy_path is not None:
            profile_locomotion["policy_path"] = Path(policy_path)
        locomotion = LocomotionConfig(**profile_locomotion)
        config = replace(self.config, locomotion=locomotion)
        return replace(
            self,
            policy_id=policy_id,
            config=config,
            canonical_backend_id=_canonical_backend_id(self.id, {"locomotion": {"mode": locomotion.mode}}),
        )


class EpisodeCatalog:
    """Ordered lookup over the six canonical local episodes."""

    def __init__(self, specs: Iterable[LocalEpisodeSpec]) -> None:
        self._specs = {spec.id: spec for spec in specs}
        if tuple(self._specs) != DEFAULT_EPISODE_IDS:
            missing = [episode_id for episode_id in DEFAULT_EPISODE_IDS if episode_id not in self._specs]
            extra = [episode_id for episode_id in self._specs if episode_id not in DEFAULT_EPISODE_IDS]
            raise EpisodeCatalogError(
                f"expected exactly the canonical six episodes; missing={missing}, extra={extra}"
            )

    def __iter__(self) -> Iterator[LocalEpisodeSpec]:
        for episode_id in DEFAULT_EPISODE_IDS:
            yield self._specs[episode_id]

    def __len__(self) -> int:
        return len(self._specs)

    @property
    def episode_ids(self) -> tuple[str, ...]:
        return DEFAULT_EPISODE_IDS

    def get(self, episode_id: str) -> LocalEpisodeSpec:
        try:
            return self._specs[episode_id]
        except KeyError as exc:
            raise EpisodeCatalogError(f"unknown local episode id: {episode_id}") from exc

    def select(
        self,
        episode_ids: Sequence[str] | None = None,
        *,
        robot_id: str | None = None,
        policy_id: str | None = None,
        policy_path: Path | None = None,
    ) -> tuple[LocalEpisodeSpec, ...]:
        if robot_id is not None and robot_id not in ROBOT_IDS:
            raise EpisodeCatalogError(f"unknown robot id: {robot_id}")
        effective_policy_id = policy_id or (DEFAULT_POLICY_BY_ROBOT[robot_id] if robot_id else None)
        if episode_ids is None or len(episode_ids) == 0:
            specs = tuple(spec for spec in self if robot_id is None or spec.robot_id == robot_id)
        else:
            specs = tuple(self.get(episode_id) for episode_id in episode_ids)
        if robot_id is not None:
            wrong_robot = [spec.id for spec in specs if spec.robot_id != robot_id]
            if wrong_robot:
                raise EpisodeCatalogError(
                    f"selected episodes do not belong to robot {robot_id}: {wrong_robot}"
                )
        if effective_policy_id is None:
            return specs
        return tuple(spec.with_policy(effective_policy_id, policy_path=policy_path) for spec in specs)


def load_default_catalog(config_dir: Path | str | None = None) -> EpisodeCatalog:
    root = _repo_root()
    directory = Path(config_dir) if config_dir is not None else root / "g1_slam" / "config" / "episodes"
    specs = tuple(_load_episode_spec(directory / f"{episode_id}.json") for episode_id in DEFAULT_EPISODE_IDS)
    return EpisodeCatalog(specs)


def _load_episode_spec(path: Path) -> LocalEpisodeSpec:
    if not path.exists():
        raise EpisodeCatalogError(f"missing canonical episode config: {path}")
    raw_bytes = path.read_bytes()
    raw_config = json.loads(raw_bytes.decode("utf-8"))
    metadata = raw_config.get("episode", {})
    episode_id = str(metadata.get("id", path.stem))
    robot_id = _episode_robot_id(episode_id)
    policy_id = DEFAULT_POLICY_BY_ROBOT[robot_id]
    return LocalEpisodeSpec(
        id=episode_id,
        title=str(metadata.get("title", episode_id)),
        description=str(metadata.get("description", "")),
        path=path,
        checksum_sha256=hashlib.sha256(raw_bytes).hexdigest(),
        raw_config=raw_config,
        config=load_navigation_config(path),
        robot_id=robot_id,
        policy_id=policy_id,
        robot_selector=_robot_selector(robot_id),
        canonical_backend_id=_canonical_backend_id(episode_id, raw_config),
    )


def _episode_robot_id(episode_id: str) -> str:
    for robot_id in ROBOT_IDS:
        if episode_id.startswith(f"{robot_id}_"):
            return robot_id
    raise EpisodeCatalogError(f"episode id does not start with a known robot id: {episode_id}")


def _robot_selector(robot_id: str) -> str:
    if robot_id == "go2":
        return "official_go2"
    if robot_id == "g1":
        return "official_g1"
    raise EpisodeCatalogError(f"unknown robot id: {robot_id}")


def _canonical_backend_id(episode_id: str, raw_config: Mapping[str, Any]) -> str:
    locomotion_mode = raw_config.get("locomotion", {}).get("mode")
    if locomotion_mode == "robojudo":
        return "g1_robojudo"
    if episode_id.startswith("go2_") and locomotion_mode == "policy":
        return "go2_mujoco_onnx"
    return "g1_slam_kinematic"


def _policy_profile_for(robot_id: str, policy_id: str) -> dict[str, Any]:
    try:
        profile = POLICY_PROFILES[policy_id]
    except KeyError as exc:
        raise EpisodeCatalogError(f"unknown policy id: {policy_id}") from exc
    if profile["robot_id"] != robot_id:
        raise EpisodeCatalogError(f"policy {policy_id} is for {profile['robot_id']}, not {robot_id}")
    return profile


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]

"""Catalog for the six canonical `g1_slam` validation episodes.

The catalog is deliberately small and file-backed. Each entry points at one of
the checked-in JSON configs, stores a checksum of the exact bytes used for the
run, and preserves the parsed `g1_slam` navigation config for execution.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from g1_slam.config import NavigationConfig, load_navigation_config

DEFAULT_EPISODE_IDS: tuple[str, ...] = (
    "g1_approach_user",
    "g1_lateral_open",
    "g1_lateral_static_dynamic_obstacles",
    "go2_approach_user",
    "go2_lateral_open",
    "go2_lateral_static_dynamic_obstacles",
)


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
    robot_selector: str
    canonical_backend_id: str
    role_inventory: tuple[dict[str, Any], ...] = ()

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
            "robot_selector": self.robot_selector,
            "canonical_backend_id": self.canonical_backend_id,
            "locomotion_mode": self.locomotion_mode,
            "role_inventory": self.role_inventory,
            "start": {
                "x": self.config.start.x,
                "y": self.config.start.y,
                "yaw": self.config.start.yaw,
            },
            "goal": {"x": self.config.goal[0], "y": self.config.goal[1]},
            "dynamic_obstacles": dict(self.raw_config.get("dynamic_obstacles", {})),
            "visualization": dict(self.raw_config.get("visualization", {})),
        }


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

    def select(self, episode_ids: Sequence[str] | None = None) -> tuple[LocalEpisodeSpec, ...]:
        if episode_ids is None or len(episode_ids) == 0:
            return tuple(self)
        return tuple(self.get(episode_id) for episode_id in episode_ids)


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
    return LocalEpisodeSpec(
        id=episode_id,
        title=str(metadata.get("title", episode_id)),
        description=str(metadata.get("description", "")),
        path=path,
        checksum_sha256=hashlib.sha256(raw_bytes).hexdigest(),
        raw_config=raw_config,
        config=load_navigation_config(path),
        robot_selector=_robot_selector(episode_id, raw_config),
        canonical_backend_id=_canonical_backend_id(episode_id, raw_config),
        role_inventory=_role_inventory(episode_id, raw_config),
    )


def _robot_selector(episode_id: str, raw_config: Mapping[str, Any]) -> str:
    if episode_id.startswith("go2_"):
        return "official_go2"
    if raw_config.get("locomotion", {}).get("mode") == "robojudo":
        return "official_g1"
    return "kinematic"


def _canonical_backend_id(episode_id: str, raw_config: Mapping[str, Any]) -> str:
    locomotion_mode = raw_config.get("locomotion", {}).get("mode")
    if locomotion_mode == "robojudo":
        return "g1_robojudo"
    if episode_id.startswith("go2_") and locomotion_mode == "policy":
        return "go2_mujoco_onnx"
    return "g1_slam_kinematic"


def _role_inventory(episode_id: str, raw_config: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    roles: list[dict[str, Any]] = []
    if episode_id.endswith("_approach_user"):
        roles.append(
            {
                "id": "target_user",
                "type": "human",
                "role": "target",
                "source": "episode_goal",
                "publicly_revealed": True,
            }
        )
    dynamic = raw_config.get("dynamic_obstacles", {})
    mode = str(dynamic.get("mode", "blue_cylinders" if dynamic.get("blue_cylinders") else "none"))
    normalized_mode = mode.replace("-", "_")
    default_dynamic_count = 3 if normalized_mode in {
        "blue",
        "blue_cylinder",
        "blue_cylinders",
        "cylinders",
        "npc",
        "npcs",
        "people",
        "persons",
        "pedestrians",
    } else 0
    count = int(dynamic.get("count", dynamic.get("blue_cylinder_count", default_dynamic_count)) or 0)
    if normalized_mode in {"npc", "npcs", "people", "persons", "pedestrians"}:
        roles.extend(
            {
                "id": f"person_npc_{index}",
                "type": "human",
                "role": "bystander",
                "source": "dynamic_obstacle",
                "publicly_revealed": True,
            }
            for index in range(count)
        )
    elif normalized_mode in {"blue", "cylinders", "blue_cylinder", "blue_cylinders"}:
        roles.extend(
            {
                "id": f"blue_cylinder_{index}",
                "type": "obstacle",
                "role": "obstacle",
                "source": "dynamic_obstacle",
                "publicly_revealed": True,
            }
            for index in range(count)
        )
    static_obstacles = raw_config.get("world", {}).get("obstacles", ())
    roles.extend(
        {
            "id": f"static_obstacle_{index}",
            "type": "obstacle",
            "role": "obstacle",
            "source": "world_obstacle",
            "publicly_revealed": True,
        }
        for index, _obstacle in enumerate(static_obstacles)
    )
    return tuple(roles)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]

"""Normalize g1_slam RoboJudo demo configs into robot-neutral episode packs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .loader import episode_pack_from_mapping, validate_episode_pack
from .models import EpisodePack, EpisodePackError

EPISODE_PAIRS = (
    ("approach_user", "obstacle_navigation", "approach_user"),
    ("lateral_open", "obstacle_navigation", "lateral_open"),
    (
        "lateral_static_dynamic_obstacles",
        "human_obstacle_navigation",
        "static_dynamic_obstacles",
    ),
)


def default_robojudo_config_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "g1_slam" / "config" / "episodes"


def load_robojudo_navigation_pack(config_dir: Path | None = None) -> EpisodePack:
    """Load paired G1/Go2 demo configs as one robot-neutral validation pack."""

    config_dir = config_dir or default_robojudo_config_dir()
    pack = episode_pack_from_mapping(robojudo_navigation_pack_mapping(config_dir))
    validate_episode_pack(pack)
    return pack


def robojudo_navigation_pack_mapping(config_dir: Path | None = None) -> dict[str, Any]:
    config_dir = config_dir or default_robojudo_config_dir()
    tiers = []
    for suffix, scenario_type, tier_id in EPISODE_PAIRS:
        g1 = _load_config(config_dir / f"g1_{suffix}.json")
        go2 = _load_config(config_dir / f"go2_{suffix}.json")
        _assert_shared_geometry(suffix, g1, go2)
        tiers.append(
            {
                "id": tier_id,
                "episodes": [_episode_from_pair(suffix, scenario_type, g1, go2)],
            }
        )
    return {
        "version": 1,
        "id": "robojudo_navigation_validation",
        "metadata": {
            "source": "g1_slam/config/episodes",
            "normalization": "Robot-neutral episode geometry; robot policy details retained as metadata.",
        },
        "tiers": tiers,
    }


def _load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise EpisodePackError(f"RoboJudo episode config path does not exist: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise EpisodePackError(f"RoboJudo episode config root must be a mapping: {path}")
    return data


def _assert_shared_geometry(suffix: str, left: dict[str, Any], right: dict[str, Any]) -> None:
    for key in ("start", "goal"):
        if left.get(key) != right.get(key):
            raise EpisodePackError(f"RoboJudo {suffix} {key} differs between robots")
    if _world_geometry(left) != _world_geometry(right):
        raise EpisodePackError(f"RoboJudo {suffix} world geometry differs between robots")
    if _dynamic_geometry(left) != _dynamic_geometry(right):
        raise EpisodePackError(f"RoboJudo {suffix} dynamic geometry differs between robots")


def _world_geometry(config: dict[str, Any]) -> dict[str, Any]:
    world = dict(config.get("world", {}))
    return {
        "bounds": {
            "x_min": world.get("x_min"),
            "y_min": world.get("y_min"),
            "x_max": world.get("x_max"),
            "y_max": world.get("y_max"),
        },
        "obstacles": world.get("obstacles", []),
    }


def _dynamic_geometry(config: dict[str, Any]) -> dict[str, Any]:
    dynamic = dict(config.get("dynamic_obstacles", {}))
    return {
        "blue_cylinders": dynamic.get("blue_cylinders", False),
        "blue_cylinder_seed": dynamic.get("blue_cylinder_seed", 7),
        "blue_cylinder_count": dynamic.get("blue_cylinder_count", 0),
    }


def _episode_from_pair(
    suffix: str,
    scenario_type: str,
    g1: dict[str, Any],
    go2: dict[str, Any],
) -> dict[str, Any]:
    world = dict(g1.get("world", {}))
    dynamic = dict(g1.get("dynamic_obstacles", {}))
    controller = dict(g1.get("controller", {}))
    episode: dict[str, Any] = {
        "id": suffix,
        "scenario_type": scenario_type,
        "robot_start": _pose(g1["start"]),
        "goal": _goal(g1["goal"], controller),
        "bounds": [world["x_min"], world["y_min"], world["x_max"], world["y_max"]],
        "max_steps": max(int(g1.get("steps", 0)), int(go2.get("steps", 0))),
        "control_dt": float(g1.get("control_dt", go2.get("control_dt", 0.05))),
        "metadata": {
            "source_episode_ids": {
                "g1": g1["episode"]["id"],
                "go2": go2["episode"]["id"],
            },
            "source_steps": {
                "g1": int(g1.get("steps", 0)),
                "go2": int(go2.get("steps", 0)),
            },
            "robot_controller_profiles": {
                "g1": _robot_source_profile(g1),
                "go2": _robot_source_profile(go2),
            },
        },
    }
    obstacles = [_obstacle(index, item) for index, item in enumerate(world.get("obstacles", []))]
    if obstacles:
        episode["obstacles"] = obstacles
    if dynamic.get("blue_cylinders", False):
        episode["metadata"].update(
            {
                "dynamic_seed": int(dynamic.get("blue_cylinder_seed", 7)),
                "dynamic_count": int(dynamic.get("blue_cylinder_count", 8)),
            }
        )
    return episode


def _pose(data: dict[str, Any]) -> dict[str, float]:
    return {
        "x": float(data["x"]),
        "y": float(data["y"]),
        "yaw": float(data.get("yaw", 0.0)),
    }


def _goal(data: dict[str, Any], controller: dict[str, Any]) -> dict[str, float]:
    goal = {
        "x": float(data["x"]),
        "y": float(data["y"]),
    }
    if "goal_tolerance" in controller:
        goal["stop_distance_m"] = float(controller["goal_tolerance"])
    return goal


def _obstacle(index: int, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"static_box_{index + 1}",
        "shape": "rectangle",
        "x_min": float(data["x_min"]),
        "y_min": float(data["y_min"]),
        "x_max": float(data["x_max"]),
        "y_max": float(data["y_max"]),
    }


def _robot_source_profile(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "controller": dict(config.get("controller", {})),
        "locomotion": dict(config.get("locomotion", {})),
        "visualization": dict(config.get("visualization", {})),
    }

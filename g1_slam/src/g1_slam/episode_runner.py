from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .config import NavigationConfig, load_navigation_config
from .dynamic_obstacles import make_default_dynamic_cylinders
from .geometry import Pose2D
from .mujoco_runner import run_mujoco_navigation
from .robojudo_backend import RoboJuDoBackendConfig, run_robojudo_navigation


@dataclass(frozen=True)
class EpisodeTraceRecord:
    episode_id: str
    robot_id: str
    policy_id: str
    status: str
    reached_goal: bool
    steps: int
    final_pose: dict[str, float] | None
    goal: tuple[float, float]
    trace_path: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class EpisodeSuiteResult:
    records: tuple[EpisodeTraceRecord, ...]


def discover_episode_configs(
    config_dir: Path,
    *,
    robot: str | None = None,
    episode_ids: tuple[str, ...] = (),
) -> tuple[Path, ...]:
    if not config_dir.exists():
        repo_relative = Path("g1_slam") / config_dir
        if repo_relative.exists():
            config_dir = repo_relative
    paths = sorted(config_dir.glob("*.json"))
    if robot:
        prefix = f"{robot}_"
        paths = [path for path in paths if path.stem.startswith(prefix)]
    if episode_ids:
        wanted = set(episode_ids)
        paths = [path for path in paths if path.stem in wanted or path.stem.removeprefix(f"{robot}_") in wanted]
    return tuple(paths)


def run_episode_suite(
    config_paths: tuple[Path, ...],
    *,
    robot_id: str,
    trace_root: Path,
    render: bool,
    robojudo_repo: Path,
    robojudo_config: str,
    continue_on_error: bool = True,
) -> EpisodeSuiteResult:
    trace_root.mkdir(parents=True, exist_ok=True)
    records = []
    for config_path in config_paths:
        try:
            record = run_episode_config(
                config_path,
                robot_id=robot_id,
                trace_root=trace_root,
                render=render,
                robojudo_repo=robojudo_repo,
                robojudo_config=robojudo_config,
            )
        except Exception as exc:
            if not continue_on_error:
                raise
            config = load_navigation_config(config_path)
            record = EpisodeTraceRecord(
                episode_id=config_path.stem,
                robot_id=robot_id,
                policy_id=_policy_id(config),
                status="episode_failure",
                reached_goal=False,
                steps=0,
                final_pose=None,
                goal=config.goal,
                error=str(exc),
            )
        records.append(record)
    summary_path = trace_root / "episode_suite_summary.json"
    summary_path.write_text(
        json.dumps({"records": [asdict(record) for record in records]}, indent=2),
        encoding="utf-8",
    )
    return EpisodeSuiteResult(records=tuple(records))


def run_episode_config(
    config_path: Path,
    *,
    robot_id: str,
    trace_root: Path,
    render: bool,
    robojudo_repo: Path,
    robojudo_config: str,
) -> EpisodeTraceRecord:
    config = load_navigation_config(config_path)
    if config.world is None:
        raise ValueError(f"episode config {config_path} does not define a world")
    trace_path = trace_root / f"{config_path.stem}-trace.json"
    if config.locomotion.mode != "robojudo":
        return _run_mujoco_episode_config(
            config,
            config_path=config_path,
            robot_id=robot_id,
            trace_path=trace_path,
            render=render,
        )
    dynamic_count = config.dynamic_obstacles.blue_cylinder_count
    result = run_robojudo_navigation(
        config.world,
        start=config.start,
        goal=config.goal,
        steps=config.steps,
        controller_config=config.controller,
        backend_config=RoboJuDoBackendConfig(
            repo_path=robojudo_repo,
            config_name=robojudo_config,
            max_vx=config.controller.max_linear_speed,
            max_vy=config.controller.max_linear_speed,
            max_yaw_rate=config.controller.max_yaw_rate,
            enable_dynamic_cylinders=config.dynamic_obstacles.blue_cylinders,
            dynamic_cylinder_seed=config.dynamic_obstacles.blue_cylinder_seed,
            dynamic_cylinder_count=dynamic_count,
            visualization=config.visualization,
        ),
        trace_path=trace_path,
        episode_id=config_path.stem,
        robot_id=robot_id,
        policy_id=_policy_id(config),
        render=render,
    )
    return EpisodeTraceRecord(
        episode_id=config_path.stem,
        robot_id=robot_id,
        policy_id=_policy_id(config),
        status=result["status"],
        reached_goal=bool(result["reached_goal"]),
        steps=int(result["step_count"]),
        final_pose=result.get("final_pose"),
        goal=config.goal,
        trace_path=str(trace_path),
    )


def _run_mujoco_episode_config(
    config: NavigationConfig,
    *,
    config_path: Path,
    robot_id: str,
    trace_path: Path,
    render: bool,
) -> EpisodeTraceRecord:
    result = run_mujoco_navigation(
        config.world,
        robot=_mujoco_robot_id(robot_id),
        model_path=None,
        start=config.start,
        goal=config.goal,
        steps=config.steps,
        controller_config=config.controller,
        locomotion_config=config.locomotion,
        render=render,
        visualization_config=config.visualization,
        dynamic_cylinders=_dynamic_cylinders(config),
        trace_path=trace_path,
        episode_id=config_path.stem,
        robot_id=robot_id,
        policy_id=_policy_id(config),
    )
    return EpisodeTraceRecord(
        episode_id=config_path.stem,
        robot_id=robot_id,
        policy_id=_policy_id(config),
        status=result["status"],
        reached_goal=bool(result["reached_goal"]),
        steps=int(result["step_count"]),
        final_pose=result.get("final_pose"),
        goal=config.goal,
        trace_path=str(trace_path),
    )


def write_dry_run_trace(path: Path, *, episode_id: str = "dry_run") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "schema": "asimovbm.sim_trace.v1",
        "episode_id": episode_id,
        "robot_id": "dry-run",
        "policy_id": "dry-run",
        "status": "dry_run",
        "reached_goal": False,
        "goal": [0.0, 0.0],
        "step_count": 1,
        "steps": [
            {
                "step_id": 0,
                "time_s": 0.0,
                "robot_pose": _pose_dict(Pose2D(0.0, 0.0, 0.0)),
                "entities": [],
                "command": {"linear": 0.0, "yaw_rate": 0.0},
                "distance_to_goal": 0.0,
            }
        ],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _policy_id(config: NavigationConfig) -> str:
    policy_path = config.locomotion.policy_path
    if policy_path is None:
        return config.locomotion.mode
    return f"{config.locomotion.mode}:{policy_path}"


def _mujoco_robot_id(robot_id: str) -> str:
    if robot_id in {"g1", "go2"}:
        return f"official_{robot_id}"
    return robot_id


def _dynamic_cylinders(config: NavigationConfig):
    if not config.dynamic_obstacles.blue_cylinders:
        return ()
    cylinders = make_default_dynamic_cylinders(config.dynamic_obstacles.blue_cylinder_seed)
    if config.dynamic_obstacles.blue_cylinder_count is not None:
        cylinders = cylinders[: max(0, config.dynamic_obstacles.blue_cylinder_count)]
    return tuple(cylinders)


def dynamic_entities_for_trace(config: NavigationConfig, sim_time: float) -> list[dict[str, Any]]:
    if not config.dynamic_obstacles.blue_cylinders:
        return []
    cylinders = make_default_dynamic_cylinders(config.dynamic_obstacles.blue_cylinder_seed)
    if config.dynamic_obstacles.blue_cylinder_count is not None:
        cylinders = cylinders[: max(0, config.dynamic_obstacles.blue_cylinder_count)]
    entities = []
    for cylinder in cylinders:
        x, y = cylinder.xy_at(sim_time)
        vx, vy = cylinder.velocity_at(sim_time)
        entities.append(
            {
                "id": cylinder.name,
                "kind": "dynamic_obstacle",
                "shape": "cylinder",
                "x": x,
                "y": y,
                "radius": cylinder.radius,
                "velocity": [vx, vy],
            }
        )
    return entities


def _pose_dict(pose: Pose2D) -> dict[str, float]:
    return {"x": pose.x, "y": pose.y, "yaw": pose.yaw}

"""Viewer-sourced real trace backends for local validation."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .backends import LocalTraceBackendError
from .catalog import LocalEpisodeSpec
from .traces import LocalEpisodeTrace, LocalStepTrace


class G1RoboJuDoRealTraceBackend:
    """Run the real G1 RoboJuDo/MuJoCo loop and consume its emitted trace."""

    backend_id = "g1_robojudo_mujoco_trace_v1"

    def run_episode(
        self,
        spec: LocalEpisodeSpec,
        *,
        iteration: int,
        viewer_enabled: bool,
        viewer_speed: float,
        camera_view: str,
    ) -> LocalEpisodeTrace:
        if spec.robot_id != "g1" or spec.locomotion_mode != "robojudo":
            raise LocalTraceBackendError(
                f"real trace backend supports only G1 RoboJuDo episodes; got "
                f"robot={spec.robot_id}, locomotion={spec.locomotion_mode}"
            )
        with tempfile.TemporaryDirectory(prefix="asimovbm-real-trace-") as tmp_dir:
            trace_path = Path(tmp_dir) / "trace.json"
            completed = self._run_viewer_backed_trace(
                spec,
                trace_path=trace_path,
                viewer_enabled=viewer_enabled,
                viewer_speed=viewer_speed,
                camera_view=camera_view,
            )
            payload = _load_real_trace_payload(trace_path)
        return _local_trace_from_robojudo_payload(
            payload,
            spec=spec,
            iteration=iteration,
            viewer_enabled=viewer_enabled,
            viewer_speed=viewer_speed,
            camera_view=camera_view,
            subprocess_result=completed,
            backend_id=self.backend_id,
        )

    def _run_viewer_backed_trace(
        self,
        spec: LocalEpisodeSpec,
        *,
        trace_path: Path,
        viewer_enabled: bool,
        viewer_speed: float,
        camera_view: str,
    ) -> subprocess.CompletedProcess[str]:
        command = [
            sys.executable,
            "-m",
            "g1_slam",
            "--config",
            spec.path.resolve().as_posix(),
            "--start",
            str(spec.config.start.x),
            str(spec.config.start.y),
            str(spec.config.start.yaw),
            "--goal",
            str(spec.config.goal[0]),
            str(spec.config.goal[1]),
            "--steps",
            str(spec.config.steps),
            "--realtime-factor",
            str(viewer_speed),
            "--camera-view",
            camera_view,
            "--start-delay",
            str(spec.config.controller.start_delay_s),
            "--locomotion",
            "robojudo",
            "--robojudo-config",
            spec.config.locomotion.robojudo_config,
            "--trace-path",
            trace_path.as_posix(),
        ]
        if viewer_enabled:
            command.append("--render")
        timeout_s = max(30.0, (spec.config.steps * 0.08 / max(viewer_speed, 0.1)) + 30.0)
        try:
            completed = subprocess.run(
                command,
                check=False,
                cwd=_g1_slam_working_directory(spec),
                timeout=timeout_s,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except subprocess.TimeoutExpired as exc:
            raise LocalTraceBackendError(
                "viewer-backed RoboJuDo trace timed out before writing usable telemetry: "
                f"{_text_tail(exc.stderr)}"
            ) from exc
        if completed.returncode != 0:
            raise LocalTraceBackendError(
                "viewer-backed RoboJuDo trace failed; no reference metrics were produced: "
                f"{_text_tail(completed.stderr)}"
            )
        return completed


def _load_real_trace_payload(trace_path: Path) -> Mapping[str, Any]:
    if not trace_path.exists():
        raise LocalTraceBackendError(
            f"viewer-backed RoboJuDo run completed but did not write trace JSON at {trace_path}"
        )
    try:
        payload = json.loads(trace_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LocalTraceBackendError(f"malformed real trace JSON: {exc.msg}") from exc
    if not isinstance(payload, Mapping):
        raise LocalTraceBackendError("real trace JSON must be an object")
    if payload.get("schema") != "asimovbm.sim_trace.v1":
        raise LocalTraceBackendError(f"unsupported real trace schema: {payload.get('schema')}")
    steps = payload.get("steps")
    if not isinstance(steps, Sequence) or isinstance(steps, (str, bytes)) or not steps:
        raise LocalTraceBackendError("real trace JSON must include non-empty steps")
    return payload


def _local_trace_from_robojudo_payload(
    payload: Mapping[str, Any],
    *,
    spec: LocalEpisodeSpec,
    iteration: int,
    viewer_enabled: bool,
    viewer_speed: float,
    camera_view: str,
    subprocess_result: subprocess.CompletedProcess[str],
    backend_id: str,
) -> LocalEpisodeTrace:
    steps_payload = payload["steps"]
    active_collision_keys: set[tuple[str, str, str]] = set()
    step_traces: list[LocalStepTrace] = []
    previous_pose: tuple[float, float, float] | None = None
    for index, raw_step in enumerate(steps_payload):
        if not isinstance(raw_step, Mapping):
            raise LocalTraceBackendError(f"real trace step {index} must be an object")
        pose = _pose_tuple(raw_step.get("robot_pose"))
        dt_s = _float_or(raw_step.get("dt_s"), _step_dt(raw_step, previous_time=step_traces[-1].time_s if step_traces else None))
        velocity = _velocity_tuple(raw_step.get("robot_velocity"), pose=pose, previous_pose=previous_pose, dt_s=dt_s)
        action = _action_tuple(raw_step.get("action", raw_step.get("command")))
        static_entities, dynamic_entities = _split_entities(raw_step.get("entities", ()))
        collisions, active_collision_keys = _collision_events(
            raw_step.get("collisions", ()),
            active_collision_keys,
            step_id=_int_or(raw_step.get("step_id"), index + 1),
        )
        step_traces.append(
            LocalStepTrace(
                step_id=_int_or(raw_step.get("step_id"), index + 1),
                time_s=_float_or(raw_step.get("time_s"), float(index + 1) * dt_s),
                dt_s=dt_s,
                robot_pose=pose,
                robot_velocity=velocity,
                action=action,
                distance_to_goal=_float_or(raw_step.get("distance_to_goal"), 0.0),
                static_entities=static_entities,
                dynamic_entities=dynamic_entities,
                collisions=collisions,
                public_observation=_mapping_or_empty(raw_step.get("public_observation")),
                qpos=_float_tuple(raw_step.get("qpos", ())),
                qvel=_float_tuple(raw_step.get("qvel", ())),
                status=str(raw_step.get("status", "running")),
                metadata={
                    "path_waypoints": len(raw_step.get("path", ()) if isinstance(raw_step.get("path"), Sequence) else ()),
                    "raw_contacts": tuple(raw_step.get("contacts", ()) if isinstance(raw_step.get("contacts"), Sequence) else ()),
                    "raw_collision_count": len(raw_step.get("collisions", ()) if isinstance(raw_step.get("collisions"), Sequence) else ()),
                },
            )
        )
        previous_pose = pose
    result_metadata = _mapping_or_empty(payload.get("metadata"))
    metadata = {
        **result_metadata,
        "reference_backend": False,
        "trace_source": result_metadata.get("trace_source", "viewer_loop" if viewer_enabled else "robojudo_loop"),
        "real_backend_verified": True,
        "backend_proof_status": "verified_in_this_run",
        "viewer_speed": viewer_speed,
        "camera_view": camera_view,
        "robojudo_config": spec.config.locomotion.robojudo_config,
        "policy_id": spec.policy_id,
        "viewer_proof": {
            "viewer_requested": viewer_enabled,
            "viewer_status": "launched" if viewer_enabled else "not_requested",
            "path": "g1_robojudo",
            "viewer_speed": viewer_speed,
            "camera_view": camera_view,
            "robojudo_config": spec.config.locomotion.robojudo_config,
            "returncode": subprocess_result.returncode,
            "stdout_tail": _text_tail(subprocess_result.stdout),
            "stderr_tail": _text_tail(subprocess_result.stderr),
        },
    }
    return LocalEpisodeTrace(
        episode_id=str(payload.get("episode_id", spec.id)),
        iteration=iteration,
        tier_id="g1_robojudo_real",
        technical_valid=True,
        terminal_status=str(payload.get("status", "timeout")),
        steps=tuple(step_traces),
        config_checksum_sha256=spec.checksum_sha256,
        config_path=spec.path.as_posix(),
        robot_selector=spec.robot_selector,
        canonical_backend_id=spec.canonical_backend_id,
        execution_backend_id=backend_id,
        viewer_mode="visible" if viewer_enabled else "headless",
        metadata=metadata,
    )


def _collision_events(
    collisions: Any,
    active_collision_keys: set[tuple[str, str, str]],
    *,
    step_id: int,
) -> tuple[tuple[dict[str, Any], ...], set[tuple[str, str, str]]]:
    if not isinstance(collisions, Sequence) or isinstance(collisions, (str, bytes)):
        return (), set()
    current_keys = {_collision_key(collision) for collision in collisions if isinstance(collision, Mapping)}
    events = []
    for collision in collisions:
        if not isinstance(collision, Mapping):
            continue
        key = _collision_key(collision)
        if key in active_collision_keys:
            continue
        events.append(
            {
                **dict(collision),
                "step_id": step_id,
                "event_key": "|".join(key),
            }
        )
    return tuple(events), current_keys


def _collision_key(collision: Mapping[str, Any]) -> tuple[str, str, str]:
    category = str(collision.get("category", collision.get("type", "contact")))
    geom_names = sorted((str(collision.get("geom1", "")), str(collision.get("geom2", ""))))
    return category, geom_names[0], geom_names[1]


def _split_entities(entities: Any) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    if not isinstance(entities, Sequence) or isinstance(entities, (str, bytes)):
        return (), ()
    static_entities: list[dict[str, Any]] = []
    dynamic_entities: list[dict[str, Any]] = []
    for entity in entities:
        if not isinstance(entity, Mapping):
            continue
        normalized = dict(entity)
        if "pose" not in normalized and {"x", "y"} <= set(normalized):
            normalized["pose"] = (float(normalized["x"]), float(normalized["y"]), 0.0)
        kind = str(normalized.get("kind", ""))
        if kind == "static_obstacle":
            static_entities.append(normalized)
        else:
            dynamic_entities.append(normalized)
    return tuple(static_entities), tuple(dynamic_entities)


def _pose_tuple(value: Any) -> tuple[float, float, float]:
    if isinstance(value, Mapping):
        return (
            _float_or(value.get("x"), 0.0),
            _float_or(value.get("y"), 0.0),
            _float_or(value.get("yaw"), 0.0),
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and len(value) >= 3:
        return (_float_or(value[0], 0.0), _float_or(value[1], 0.0), _float_or(value[2], 0.0))
    raise LocalTraceBackendError(f"invalid robot_pose in real trace step: {value!r}")


def _velocity_tuple(
    value: Any,
    *,
    pose: tuple[float, float, float],
    previous_pose: tuple[float, float, float] | None,
    dt_s: float,
) -> tuple[float, float, float]:
    if isinstance(value, Mapping):
        return (
            _float_or(value.get("vx"), 0.0),
            _float_or(value.get("vy"), 0.0),
            _float_or(value.get("yaw_rate"), 0.0),
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and len(value) >= 3:
        return (_float_or(value[0], 0.0), _float_or(value[1], 0.0), _float_or(value[2], 0.0))
    if previous_pose is None or dt_s <= 0.0:
        return (0.0, 0.0, 0.0)
    return (
        (pose[0] - previous_pose[0]) / dt_s,
        (pose[1] - previous_pose[1]) / dt_s,
        (pose[2] - previous_pose[2]) / dt_s,
    )


def _action_tuple(value: Any) -> tuple[float, float]:
    if isinstance(value, Mapping):
        return (_float_or(value.get("linear"), _float_or(value.get("vx"), 0.0)), _float_or(value.get("yaw_rate"), 0.0))
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and len(value) >= 2:
        return (_float_or(value[0], 0.0), _float_or(value[1], 0.0))
    return (0.0, 0.0)


def _step_dt(raw_step: Mapping[str, Any], *, previous_time: float | None) -> float:
    time_s = raw_step.get("time_s")
    if previous_time is not None and isinstance(time_s, int | float):
        return max(float(time_s) - previous_time, 0.0)
    return 0.02


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _float_tuple(value: Any) -> tuple[float, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(_float_or(item, 0.0) for item in value)


def _float_or(value: Any, default: float) -> float:
    if isinstance(value, int | float):
        return float(value)
    return default


def _int_or(value: Any, default: int) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return default


def _g1_slam_working_directory(spec: LocalEpisodeSpec) -> Path | None:
    if len(spec.path.parents) >= 3:
        return spec.path.parents[2]
    return None


def _text_tail(value: Any, limit: int = 1000) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return str(value)[-limit:]

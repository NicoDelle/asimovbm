"""Optional RoboJudo robot adapter for server-local validation episodes."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from asimovbm_protocol import ActionMessage
from asimovbm_server.episodes import Pose2D

from .base import RobotProfile, RobotState
from .mujoco_kinematic import RobotProfileSetupError

BackendFactory = Callable[[RobotProfile], Any]


class RoboJudoRobot:
    """Bridge the validation runner's mobile-base command contract into RoboJudo."""

    def __init__(
        self,
        profile: RobotProfile,
        *,
        backend_factory: BackendFactory | None = None,
    ) -> None:
        self.profile = profile
        factory = backend_factory or profile.metadata.get("backend_factory")
        self._backend = factory(profile) if callable(factory) else _create_backend(profile)
        self._pose = Pose2D(0.0, 0.0, 0.0)
        self._step_id = 0
        self._time_s = 0.0
        self._velocity = (0.0, 0.0, 0.0)

    def reset(self, pose: Pose2D) -> None:
        reset = getattr(self._backend, "reset", None)
        if callable(reset):
            reset()
        reborn = getattr(self._backend, "reborn", None)
        if callable(reborn):
            reborn((pose.x, pose.y, pose.yaw))
        self._pose = pose
        self._step_id = 0
        self._time_s = 0.0
        self._velocity = (0.0, 0.0, 0.0)

    def state(self) -> RobotState:
        return RobotState(
            step_id=self._step_id,
            time_s=self._time_s,
            pose=self._pose,
            velocity=self._velocity,
            metadata=self.profile.setup_metadata(),
        )

    def apply_action(self, action: ActionMessage, dt: float) -> RobotState:
        if not action.valid:
            raise ValueError(action.invalid_reason or "invalid action")
        if len(action.action) != 2:
            raise ValueError("RoboJudo validation actions require [linear_velocity, yaw_rate]")
        linear_velocity = float(action.action[0])
        yaw_rate = float(action.action[1])
        command = _command(linear_velocity, 0.0, yaw_rate)
        set_command = getattr(self._backend, "set_command", None)
        if callable(set_command):
            set_command(command)
        step = getattr(self._backend, "step", None)
        if callable(step):
            step()
        self._pose = _backend_pose(self._backend, self._pose)
        self._velocity = (linear_velocity, 0.0, yaw_rate)
        self._step_id += 1
        self._time_s += _backend_dt(self._backend, dt)
        return self.state()

    def viewer_target(self) -> tuple[Any, Any] | None:
        pipeline = getattr(self._backend, "pipeline", None)
        env = getattr(pipeline, "env", None)
        model = getattr(env, "model", None)
        data = getattr(env, "data", None)
        if model is None or data is None:
            return None
        return model, data


def _create_backend(profile: RobotProfile) -> Any:
    repo_path = _resolved_optional_path(profile, "robojudo_repo_path")
    if repo_path is None or not repo_path.exists():
        raise RobotProfileSetupError(
            f"robot profile {profile.id!r} requires RoboJudo checkout at {repo_path}; "
            "install RoboJudo or use a kinematic/marker profile"
        )
    policy_path = _resolved_optional_path(profile, "policy_path")
    if policy_path is not None and not policy_path.exists():
        raise RobotProfileSetupError(
            f"robot profile {profile.id!r} requires policy path {policy_path}; "
            "install the policy asset or use a kinematic/marker profile"
        )
    try:
        from g1_slam.robojudo_backend import RoboJuDoBackend, RoboJuDoBackendConfig
    except ModuleNotFoundError as exc:
        raise RobotProfileSetupError(
            f"robot profile {profile.id!r} requires the g1_slam RoboJudo backend"
        ) from exc
    config = RoboJuDoBackendConfig(
        repo_path=repo_path,
        config_name=str(profile.metadata.get("config_name", "g1")),
        visualization=bool(profile.metadata.get("visualization", False)),
    )
    return RoboJuDoBackend(config)


def _resolved_optional_path(profile: RobotProfile, key: str) -> Path | None:
    raw = profile.metadata.get(key)
    if not raw:
        return None
    path = Path(str(raw))
    if path.is_absolute():
        return path
    return Path(__file__).resolve().parents[3] / path


def _command(vx: float, vy: float, yaw_rate: float) -> Any:
    try:
        from g1_slam.robojudo_backend import RoboJuDoCommand
    except ModuleNotFoundError:
        return {"vx": vx, "vy": vy, "yaw_rate": yaw_rate}
    return RoboJuDoCommand(vx=vx, vy=vy, yaw_rate=yaw_rate)


def _backend_pose(backend: Any, fallback: Pose2D) -> Pose2D:
    pose = getattr(backend, "pose", None)
    if not callable(pose):
        return fallback
    value = pose()
    if isinstance(value, Pose2D):
        return value
    if isinstance(value, dict):
        return Pose2D(float(value["x"]), float(value["y"]), float(value.get("yaw", 0.0)))
    x, y, yaw = value
    return Pose2D(float(x), float(y), float(yaw))


def _backend_dt(backend: Any, fallback: float) -> float:
    pipeline = getattr(backend, "pipeline", None)
    dt = getattr(pipeline, "dt", None)
    if dt is None:
        return fallback
    return float(dt)

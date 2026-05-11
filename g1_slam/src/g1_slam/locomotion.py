from __future__ import annotations

from dataclasses import dataclass
from math import cos, sin, tau
from pathlib import Path

from .config import LocomotionConfig
from .controller import VelocityCommand


G1_29DOF_JOINT_ORDER = (
    "left_hip_pitch",
    "left_hip_roll",
    "left_hip_yaw",
    "left_knee",
    "left_ankle_pitch",
    "left_ankle_roll",
    "right_hip_pitch",
    "right_hip_roll",
    "right_hip_yaw",
    "right_knee",
    "right_ankle_pitch",
    "right_ankle_roll",
    "waist_yaw",
    "waist_roll",
    "waist_pitch",
    "left_shoulder_pitch",
    "left_shoulder_roll",
    "left_shoulder_yaw",
    "left_elbow",
    "left_wrist_roll",
    "left_wrist_pitch",
    "left_wrist_yaw",
    "right_shoulder_pitch",
    "right_shoulder_roll",
    "right_shoulder_yaw",
    "right_elbow",
    "right_wrist_roll",
    "right_wrist_pitch",
    "right_wrist_yaw",
)

GO2_MJLAB_JOINT_ORDER = (
    "FL_hip",
    "FL_thigh",
    "FL_calf",
    "FR_hip",
    "FR_thigh",
    "FR_calf",
    "RL_hip",
    "RL_thigh",
    "RL_calf",
    "RR_hip",
    "RR_thigh",
    "RR_calf",
)

GO2_MJLAB_DEFAULT_JOINT_POS = (
    -0.1,
    0.9,
    -1.8,
    0.1,
    0.9,
    -1.8,
    -0.1,
    0.9,
    -1.8,
    0.1,
    0.9,
    -1.8,
)

UNITREE_RL_MJLAB_GO2_PROFILE = "unitree_rl_mjlab_go2"
DIAS_AI_MASTER_GO2_VELOCITY_FLAT_PROFILE = "dias_ai_master_go2_velocity_flat"
GO2_MJLAB_GAIT_PERIOD_SECONDS = 0.6
GO2_MJLAB_STEP_DT_SECONDS = 0.02


@dataclass(frozen=True)
class JointBinding:
    name: str
    actuator_id: int
    qpos_address: int
    qvel_address: int
    ctrl_min: float
    ctrl_max: float
    default_angle: float


class OnnxPolicyLocomotion:
    def __init__(self, mujoco, model, config: LocomotionConfig) -> None:
        if config.policy_path is None:
            raise ValueError("locomotion.policy_path is required when locomotion.mode is 'policy'")
        policy_path = Path(config.policy_path)
        if not policy_path.exists():
            raise FileNotFoundError(
                f"ONNX policy not found: {policy_path}. "
                "Place your policy there or change locomotion.policy_path in the navigation config."
            )
        if _is_git_lfs_pointer(policy_path):
            raise RuntimeError(
                f"{policy_path} is a Git LFS pointer, not the ONNX model binary. "
                "Download the real Hugging Face files before running policy locomotion, "
                "for example with: huggingface-cli download diasAiMaster/unitree-go2-velocity-flat "
                "policy.onnx policy.onnx.data params/deploy.yaml "
                "--local-dir policies/go2/unitree_rl_mjlab"
            )
        external_data_path = policy_path.with_suffix(policy_path.suffix + ".data")
        if external_data_path.exists() and _is_git_lfs_pointer(external_data_path):
            raise RuntimeError(
                f"{external_data_path} is a Git LFS pointer, not the ONNX external data file. "
                "Re-download policy.onnx and policy.onnx.data from Hugging Face before running."
            )
        try:
            import onnxruntime as ort
        except ModuleNotFoundError as exc:
            raise RuntimeError("Install onnxruntime to use locomotion.mode='policy': pip install onnxruntime") from exc

        self.mujoco = mujoco
        self.config = config
        self.bindings = _build_policy_bindings(mujoco, model, config)
        self.previous_action = [0.0 for _ in self.bindings]
        self.step_count = 0
        self.session = ort.InferenceSession(str(policy_path), providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name

    def step(self, data, command: VelocityCommand) -> None:
        observation = self._observation(data, command)
        action = self._infer(observation)
        self._apply_pd(data, action)
        self.previous_action = action
        self.step_count += 1

    def _observation(self, data, command: VelocityCommand) -> list[float]:
        if self.config.observation_profile in GO2_MJLAB_PROFILES:
            obs = self._unitree_rl_mjlab_go2_observation(data, command)
            return self._fit_observation_size(obs)

        obs = [
            command.linear,
            0.0,
            command.yaw_rate,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            -1.0,
        ]
        for binding in self.bindings:
            obs.append(float(data.qpos[binding.qpos_address] - binding.default_angle))
        for binding in self.bindings:
            obs.append(float(data.qvel[binding.qvel_address]))
        obs.extend(self.previous_action)

        return self._fit_observation_size(obs)

    def _fit_observation_size(self, obs: list[float]) -> list[float]:
        if self.config.observation_size is None:
            return obs
        if len(obs) < self.config.observation_size:
            obs.extend([0.0] * (self.config.observation_size - len(obs)))
        return obs[: self.config.observation_size]

    def _unitree_rl_mjlab_go2_observation(self, data, command: VelocityCommand) -> list[float]:
        obs = []
        obs.extend(_base_angular_velocity(data))
        obs.extend(_projected_gravity(data))
        obs.extend([command.linear, 0.0, command.yaw_rate])
        if self.config.observation_profile == UNITREE_RL_MJLAB_GO2_PROFILE:
            obs.extend(_gait_phase(self.step_count, command))
        for binding in self.bindings:
            obs.append(float(data.qpos[binding.qpos_address] - binding.default_angle))
        for binding in self.bindings:
            obs.append(float(data.qvel[binding.qvel_address]))
        obs.extend(self.previous_action)
        return obs

    def _infer(self, observation: list[float]) -> list[float]:
        try:
            import numpy as np
        except ModuleNotFoundError as exc:
            raise RuntimeError("Install numpy to run the ONNX policy: pip install numpy") from exc

        raw_output = self.session.run([self.output_name], {self.input_name: np.array([observation], dtype=np.float32)})[0]
        values = raw_output.reshape(-1).astype(float).tolist()
        if len(values) < len(self.bindings):
            values.extend([0.0] * (len(self.bindings) - len(values)))
        return values[: len(self.bindings)]

    def _apply_pd(self, data, action: list[float]) -> None:
        for binding, normalized_action in zip(self.bindings, action, strict=True):
            target = binding.default_angle + self.config.action_scale * normalized_action
            qpos = float(data.qpos[binding.qpos_address])
            qvel = float(data.qvel[binding.qvel_address])
            torque = self.config.kp * (target - qpos) - self.config.kd * qvel
            data.ctrl[binding.actuator_id] = max(binding.ctrl_min, min(binding.ctrl_max, torque))


def _build_policy_bindings(mujoco, model, config: LocomotionConfig) -> list[JointBinding]:
    if config.observation_profile in GO2_MJLAB_PROFILES:
        bindings = _build_named_joint_bindings(
            mujoco,
            model,
            GO2_MJLAB_JOINT_ORDER,
            GO2_MJLAB_DEFAULT_JOINT_POS,
        )
        if bindings:
            return bindings

    g1_bindings = _build_named_joint_bindings(mujoco, model, G1_29DOF_JOINT_ORDER)
    if g1_bindings:
        return g1_bindings
    bindings = _build_actuator_joint_bindings(mujoco, model)
    if not bindings:
        raise RuntimeError("No MuJoCo actuators compatible with an ONNX policy were found in the model.")
    return bindings


GO2_MJLAB_PROFILES = {
    UNITREE_RL_MJLAB_GO2_PROFILE,
    DIAS_AI_MASTER_GO2_VELOCITY_FLAT_PROFILE,
}


def _build_named_joint_bindings(
    mujoco,
    model,
    joint_names: tuple[str, ...],
    default_angles: tuple[float, ...] | None = None,
) -> list[JointBinding]:
    bindings: list[JointBinding] = []
    for index, name in enumerate(joint_names):
        actuator_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, name)
        joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, f"{name}_joint")
        if actuator_id < 0 or joint_id < 0:
            continue
        default_angle = (
            default_angles[index]
            if default_angles is not None
            else _default_joint_angle(mujoco, model, joint_id)
        )
        bindings.append(
            _joint_binding(
                mujoco,
                model,
                name,
                actuator_id,
                joint_id,
                default_angle=default_angle,
            )
        )
    return bindings


def _build_actuator_joint_bindings(mujoco, model) -> list[JointBinding]:
    bindings: list[JointBinding] = []
    for actuator_id in range(model.nu):
        joint_id = int(model.actuator_trnid[actuator_id][0])
        if joint_id < 0 or int(model.jnt_type[joint_id]) == int(mujoco.mjtJoint.mjJNT_FREE):
            continue
        name = _name_for_id(mujoco, model, mujoco.mjtObj.mjOBJ_ACTUATOR, actuator_id)
        bindings.append(
            _joint_binding(
                mujoco,
                model,
                name,
                actuator_id,
                joint_id,
                default_angle=_default_joint_angle(mujoco, model, joint_id),
            )
        )
    return bindings


def _joint_binding(
    mujoco,
    model,
    name: str,
    actuator_id: int,
    joint_id: int,
    *,
    default_angle: float,
) -> JointBinding:
    return JointBinding(
        name=name,
        actuator_id=int(actuator_id),
        qpos_address=int(model.jnt_qposadr[joint_id]),
        qvel_address=int(model.jnt_dofadr[joint_id]),
        ctrl_min=float(model.actuator_ctrlrange[actuator_id][0]),
        ctrl_max=float(model.actuator_ctrlrange[actuator_id][1]),
        default_angle=default_angle,
    )


def _default_joint_angle(mujoco, model, joint_id: int) -> float:
    qpos_address = int(model.jnt_qposadr[joint_id])
    home_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, "home")
    if home_id >= 0:
        return float(model.key_qpos[home_id][qpos_address])
    return 0.0


def _name_for_id(mujoco, model, objtype, obj_id: int) -> str:
    raw_name = mujoco.mj_id2name(model, objtype, obj_id)
    return raw_name if raw_name is not None else f"actuator_{obj_id}"


def _base_angular_velocity(data) -> list[float]:
    qvel_address = 0
    return [
        float(data.qvel[qvel_address + 3]),
        float(data.qvel[qvel_address + 4]),
        float(data.qvel[qvel_address + 5]),
    ]


def _projected_gravity(data) -> list[float]:
    qpos_address = 0
    qw = float(data.qpos[qpos_address + 3])
    qx = float(data.qpos[qpos_address + 4])
    qy = float(data.qpos[qpos_address + 5])
    qz = float(data.qpos[qpos_address + 6])
    return _rotate_world_vector_into_body((0.0, 0.0, -1.0), (qw, qx, qy, qz))


def _rotate_world_vector_into_body(
    vector: tuple[float, float, float],
    quat_wxyz: tuple[float, float, float, float],
) -> list[float]:
    qw, qx, qy, qz = quat_wxyz
    vx, vy, vz = vector
    return [
        (1 - 2 * (qy * qy + qz * qz)) * vx
        + 2 * (qx * qy + qw * qz) * vy
        + 2 * (qx * qz - qw * qy) * vz,
        2 * (qx * qy - qw * qz) * vx
        + (1 - 2 * (qx * qx + qz * qz)) * vy
        + 2 * (qy * qz + qw * qx) * vz,
        2 * (qx * qz + qw * qy) * vx
        + 2 * (qy * qz - qw * qx) * vy
        + (1 - 2 * (qx * qx + qy * qy)) * vz,
    ]


def _gait_phase(step_count: int, command: VelocityCommand) -> list[float]:
    if abs(command.linear) < 0.1 and abs(command.yaw_rate) < 0.1:
        return [0.0, 0.0]
    phase = ((step_count * GO2_MJLAB_STEP_DT_SECONDS) % GO2_MJLAB_GAIT_PERIOD_SECONDS) / (
        GO2_MJLAB_GAIT_PERIOD_SECONDS
    )
    angle = phase * tau
    return [sin(angle), cos(angle)]


def _is_git_lfs_pointer(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            prefix = fh.read(128)
    except OSError:
        return False
    return prefix.startswith(b"version https://git-lfs.github.com/spec/v1")

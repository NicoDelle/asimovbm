from __future__ import annotations

from dataclasses import dataclass
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
                f"No se encontro la policy ONNX: {policy_path}. "
                "Coloca tu policy ahi o cambia locomotion.policy_path en config/navigation.json."
            )
        try:
            import onnxruntime as ort
        except ModuleNotFoundError as exc:
            raise RuntimeError("Instala onnxruntime para usar locomotion.mode='policy': pip install onnxruntime") from exc

        self.mujoco = mujoco
        self.config = config
        self.bindings = _build_g1_bindings(mujoco, model)
        self.previous_action = [0.0 for _ in self.bindings]
        self.session = ort.InferenceSession(str(policy_path), providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name

    def step(self, data, command: VelocityCommand) -> None:
        observation = self._observation(data, command)
        action = self._infer(observation)
        self._apply_pd(data, action)
        self.previous_action = action

    def _observation(self, data, command: VelocityCommand) -> list[float]:
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

        if self.config.observation_size is None:
            return obs
        if len(obs) < self.config.observation_size:
            obs.extend([0.0] * (self.config.observation_size - len(obs)))
        return obs[: self.config.observation_size]

    def _infer(self, observation: list[float]) -> list[float]:
        try:
            import numpy as np
        except ModuleNotFoundError as exc:
            raise RuntimeError("Instala numpy para ejecutar la policy ONNX: pip install numpy") from exc

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


def _build_g1_bindings(mujoco, model) -> list[JointBinding]:
    bindings: list[JointBinding] = []
    for name in G1_29DOF_JOINT_ORDER:
        actuator_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, name)
        joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, f"{name}_joint")
        if actuator_id < 0 or joint_id < 0:
            continue
        bindings.append(
            JointBinding(
                name=name,
                actuator_id=int(actuator_id),
                qpos_address=int(model.jnt_qposadr[joint_id]),
                qvel_address=int(model.jnt_dofadr[joint_id]),
                ctrl_min=float(model.actuator_ctrlrange[actuator_id][0]),
                ctrl_max=float(model.actuator_ctrlrange[actuator_id][1]),
                default_angle=0.0,
            )
        )
    if not bindings:
        raise RuntimeError("No se encontraron actuadores compatibles con el G1 oficial en el modelo MuJoCo.")
    return bindings

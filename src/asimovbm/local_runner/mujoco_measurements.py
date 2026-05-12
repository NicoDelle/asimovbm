"""MuJoCo measurement extraction helpers.

This module intentionally accepts an injected MuJoCo API object instead of
importing :mod:`mujoco` at module import time. The local runner must remain
usable in dependency-light environments, while optional MuJoCo tests can pass
the real package when it is installed.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any


class MeasurementExtractionError(RuntimeError):
    """Raised when a required MuJoCo measurement cannot be extracted."""


def refresh_measurement_data(mujoco: Any, model: Any, data: Any) -> None:
    """Refresh MuJoCo derived fields before reading measurement data.

    After a step advances generalized state, Cartesian body/geom fields,
    contacts, and sensors must be refreshed before trace extraction reads them.
    Tests inject a fake API here so stale-field bugs are visible without a real
    MuJoCo install.
    """

    mujoco.mj_forward(model, data)


def extract_mujoco_measurement(
    *,
    mujoco: Any,
    model: Any,
    data: Any,
    robot_body_name: str,
    freejoint_name: str | None = None,
    measurement_proof_level: str = "fake_model_data",
    refresh: bool = True,
) -> dict[str, Any]:
    if refresh:
        refresh_measurement_data(mujoco, model, data)

    body_id = _name_to_id(mujoco, model, _object_type(mujoco, "mjOBJ_BODY"), robot_body_name)
    if body_id < 0:
        raise MeasurementExtractionError(f"unknown MuJoCo body: {robot_body_name}")

    qpos: tuple[float, ...] = ()
    qvel: tuple[float, ...] = ()
    if freejoint_name is not None:
        joint_id = _name_to_id(mujoco, model, _object_type(mujoco, "mjOBJ_JOINT"), freejoint_name)
        if joint_id < 0:
            raise MeasurementExtractionError(f"unknown MuJoCo joint: {freejoint_name}")
        qpos_adr = int(model.jnt_qposadr[joint_id])
        qvel_adr = int(model.jnt_dofadr[joint_id])
        qpos = _slice_tuple(data.qpos, qpos_adr, 7)
        qvel = _slice_tuple(data.qvel, qvel_adr, 6)

    world_position = _tuple_at(data.xpos, body_id, 3)
    world_quat = _tuple_at(data.xquat, body_id, 4)
    yaw = yaw_from_wxyz(world_quat)

    return {
        "time_s": float(getattr(data, "time", 0.0)),
        "measurement_source": "mujoco",
        "measurement_proof_level": measurement_proof_level,
        "frame_conventions": {
            "position": "world_m",
            "quaternion": "wxyz",
            "qpos_freejoint": "global_position_then_global_wxyz_quaternion",
            "qvel_freejoint": "global_linear_then_local_angular_velocity",
        },
        "robot_state": {
            "body_id": body_id,
            "body_name": robot_body_name,
            "world_position": world_position,
            "world_quaternion_wxyz": world_quat,
            "yaw_rad": yaw,
            "qpos": qpos,
            "qvel": qvel,
            "ctrl": tuple(float(value) for value in getattr(data, "ctrl", ())),
        },
        "contacts": _contacts(mujoco, model, data),
        "sensors": _sensors(mujoco, model, data),
    }


def yaw_from_wxyz(quaternion: Sequence[float]) -> float:
    if len(quaternion) != 4:
        raise MeasurementExtractionError("MuJoCo quaternion must have four wxyz values")
    w, x, y, z = (float(value) for value in quaternion)
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    return math.atan2(siny_cosp, cosy_cosp)


def yaw_from_xyzw(quaternion: Sequence[float]) -> float:
    if len(quaternion) != 4:
        raise MeasurementExtractionError("xyzw quaternion must have four values")
    x, y, z, w = (float(value) for value in quaternion)
    return yaw_from_wxyz((w, x, y, z))


def yaw_rate_from_world_yaws(*, previous_yaw: float, current_yaw: float, dt_s: float) -> float:
    if dt_s <= 0.0:
        raise MeasurementExtractionError("yaw-rate extraction requires positive dt_s")
    return _wrap_angle(float(current_yaw) - float(previous_yaw)) / dt_s


def _contacts(mujoco: Any, model: Any, data: Any) -> tuple[dict[str, Any], ...]:
    contacts: list[dict[str, Any]] = []
    geom_type = _object_type(mujoco, "mjOBJ_GEOM")
    for index in range(int(getattr(data, "ncon", 0))):
        contact = data.contact[index]
        geom1_id = int(contact.geom1)
        geom2_id = int(contact.geom2)
        contacts.append(
            {
                "geom1_id": geom1_id,
                "geom1_name": _id_to_name(mujoco, model, geom_type, geom1_id),
                "geom2_id": geom2_id,
                "geom2_name": _id_to_name(mujoco, model, geom_type, geom2_id),
                "distance_m": float(getattr(contact, "dist", 0.0)),
            }
        )
    return tuple(contacts)


def _sensors(mujoco: Any, model: Any, data: Any) -> dict[str, tuple[float, ...]]:
    sensor_count = int(getattr(model, "nsensor", 0))
    if sensor_count <= 0:
        return {}
    sensor_type = _object_type(mujoco, "mjOBJ_SENSOR")
    sensors: dict[str, tuple[float, ...]] = {}
    for sensor_id in range(sensor_count):
        name = _id_to_name(mujoco, model, sensor_type, sensor_id) or f"sensor_{sensor_id}"
        adr = int(model.sensor_adr[sensor_id])
        dim = int(model.sensor_dim[sensor_id])
        sensors[name] = _slice_tuple(data.sensordata, adr, dim)
    return sensors


def _name_to_id(mujoco: Any, model: Any, object_type: Any, name: str) -> int:
    return int(mujoco.mj_name2id(model, object_type, name))


def _id_to_name(mujoco: Any, model: Any, object_type: Any, object_id: int) -> str | None:
    if hasattr(mujoco, "mj_id2name"):
        return mujoco.mj_id2name(model, object_type, object_id)
    return None


def _object_type(mujoco: Any, name: str) -> Any:
    return getattr(mujoco.mjtObj, name)


def _tuple_at(values: Any, index: int, length: int) -> tuple[float, ...]:
    return tuple(float(value) for value in values[index][:length])


def _slice_tuple(values: Any, start: int, length: int) -> tuple[float, ...]:
    return tuple(float(values[index]) for index in range(start, start + length))


def _wrap_angle(angle: float) -> float:
    while angle > math.pi:
        angle -= 2.0 * math.pi
    while angle < -math.pi:
        angle += 2.0 * math.pi
    return angle

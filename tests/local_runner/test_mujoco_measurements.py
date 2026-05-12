from __future__ import annotations

from types import SimpleNamespace

import pytest

from asimovbm.local_runner.mujoco_measurements import (
    MeasurementExtractionError,
    extract_mujoco_measurement,
    refresh_measurement_data,
    yaw_from_wxyz,
    yaw_rate_from_world_yaws,
)


class FakeMujoco:
    mjtObj = SimpleNamespace(
        mjOBJ_BODY="body",
        mjOBJ_GEOM="geom",
        mjOBJ_JOINT="joint",
        mjOBJ_SENSOR="sensor",
    )

    def __init__(self) -> None:
        self.forward_calls = 0

    def mj_forward(self, model, data) -> None:
        self.forward_calls += 1
        data.xpos[1] = (9.0, 8.0, 7.0)
        data.xquat[1] = (1.0, 0.0, 0.0, 0.0)
        data.refreshed = True

    def mj_name2id(self, model, object_type, name: str) -> int:
        return model.name_to_id.get((object_type, name), -1)

    def mj_id2name(self, model, object_type, object_id: int) -> str | None:
        return model.id_to_name.get((object_type, object_id))


def test_extract_mujoco_measurement_refreshes_before_reading_derived_fields() -> None:
    mujoco = FakeMujoco()
    model = SimpleNamespace(
        name_to_id={
            ("body", "robot_base"): 1,
            ("joint", "root_freejoint"): 0,
            ("geom", "robot_geom"): 0,
            ("geom", "wall_geom"): 1,
            ("sensor", "rangefinder"): 0,
        },
        id_to_name={
            ("body", 1): "robot_base",
            ("geom", 0): "robot_geom",
            ("geom", 1): "wall_geom",
            ("sensor", 0): "rangefinder",
        },
        jnt_qposadr=[0],
        jnt_dofadr=[0],
        nsensor=1,
        sensor_adr=[0],
        sensor_dim=[2],
    )
    data = SimpleNamespace(
        time=1.25,
        qpos=[1.0, 2.0, 3.0, 1.0, 0.0, 0.0, 0.0],
        qvel=[0.1, 0.2, 0.3, 0.0, 0.0, 0.4],
        ctrl=[0.7, -0.2],
        xpos=[(0.0, 0.0, 0.0), (-1.0, -1.0, -1.0)],
        xquat=[(1.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)],
        ncon=1,
        contact=[SimpleNamespace(geom1=0, geom2=1, dist=0.02)],
        sensordata=[4.0, 5.0],
        refreshed=False,
    )

    snapshot = extract_mujoco_measurement(
        mujoco=mujoco,
        model=model,
        data=data,
        robot_body_name="robot_base",
        freejoint_name="root_freejoint",
    )

    assert mujoco.forward_calls == 1
    assert data.refreshed is True
    assert snapshot["time_s"] == 1.25
    assert snapshot["robot_state"]["world_position"] == (9.0, 8.0, 7.0)
    assert snapshot["robot_state"]["qpos"] == (1.0, 2.0, 3.0, 1.0, 0.0, 0.0, 0.0)
    assert snapshot["robot_state"]["qvel"] == (0.1, 0.2, 0.3, 0.0, 0.0, 0.4)
    assert snapshot["contacts"] == (
        {"geom1_id": 0, "geom1_name": "robot_geom", "geom2_id": 1, "geom2_name": "wall_geom", "distance_m": 0.02},
    )
    assert snapshot["sensors"]["rangefinder"] == (4.0, 5.0)
    assert snapshot["measurement_proof_level"] == "fake_model_data"


def test_model_without_freejoint_uses_body_pose_without_crashing() -> None:
    mujoco = FakeMujoco()
    model = SimpleNamespace(
        name_to_id={("body", "robot_base"): 1},
        id_to_name={("body", 1): "robot_base"},
        jnt_qposadr=[],
        jnt_dofadr=[],
        nsensor=0,
        sensor_adr=[],
        sensor_dim=[],
    )
    data = SimpleNamespace(
        time=0.5,
        qpos=[],
        qvel=[],
        ctrl=[],
        xpos=[(0.0, 0.0, 0.0), (1.0, 2.0, 0.0)],
        xquat=[(1.0, 0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0)],
        ncon=0,
        contact=[],
        sensordata=[],
    )

    snapshot = extract_mujoco_measurement(
        mujoco=mujoco,
        model=model,
        data=data,
        robot_body_name="robot_base",
        freejoint_name=None,
    )

    assert snapshot["robot_state"]["world_position"] == (9.0, 8.0, 7.0)
    assert snapshot["robot_state"]["qpos"] == ()
    assert snapshot["robot_state"]["qvel"] == ()
    assert snapshot["sensors"] == {}


def test_unknown_robot_body_reports_technical_failure_reason() -> None:
    with pytest.raises(MeasurementExtractionError, match="unknown MuJoCo body"):
        extract_mujoco_measurement(
            mujoco=FakeMujoco(),
            model=SimpleNamespace(name_to_id={}, id_to_name={}, nsensor=0),
            data=SimpleNamespace(time=0.0, xpos=[], xquat=[], ncon=0, contact=[], sensordata=[], ctrl=[]),
            robot_body_name="missing",
            refresh=False,
        )


def test_yaw_helpers_use_mujoco_wxyz_and_world_frame_deltas() -> None:
    assert yaw_from_wxyz((1.0, 0.0, 0.0, 0.0)) == 0.0
    assert yaw_rate_from_world_yaws(previous_yaw=0.0, current_yaw=1.0, dt_s=0.5) == 2.0


def test_refresh_measurement_data_uses_injected_mujoco_api() -> None:
    mujoco = FakeMujoco()
    data = SimpleNamespace(xpos=[(0, 0, 0), (0, 0, 0)], xquat=[(1, 0, 0, 0), (1, 0, 0, 0)])

    refresh_measurement_data(mujoco, object(), data)

    assert mujoco.forward_calls == 1

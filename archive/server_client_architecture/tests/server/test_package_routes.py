"""Package submission route tests."""

from __future__ import annotations

from .conftest import BOOTSTRAP_TOKEN


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_session(client) -> dict[str, str]:
    return client.post(
        "/sessions", json={}, headers=_bearer(BOOTSTRAP_TOKEN)
    ).json()


def _minimal_manifest() -> dict:
    return {
        "name": "testbot",
        "model": {"format": "mjcf", "path": "robot.xml"},
        "sensors": [
            {"name": "lidar", "kind": "lidar"},
            {"name": "pose", "kind": "proprioception"},
        ],
        "action_mapping": {"mode": "joint_target", "joints": ["w1", "w2"]},
        "robot_metadata": {"forward_axis": "x+"},
    }


def test_package_submission_accepts_minimal_manifest(client) -> None:
    sess = _create_session(client)
    response = client.post(
        f"/sessions/{sess['run_id']}/package",
        json=_minimal_manifest(),
        headers=_bearer(sess["run_token"]),
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "accepted"
    assert payload["settings"]["control_dt"] == 0.025


def test_package_submission_rejects_missing_token(client) -> None:
    sess = _create_session(client)
    response = client.post(
        f"/sessions/{sess['run_id']}/package",
        json=_minimal_manifest(),
    )
    assert response.status_code == 401


def test_package_submission_rejects_wrong_token(client) -> None:
    sess = _create_session(client)
    response = client.post(
        f"/sessions/{sess['run_id']}/package",
        json=_minimal_manifest(),
        headers=_bearer("wrong-token"),
    )
    assert response.status_code == 401


def test_package_rejection_returns_errors(client) -> None:
    sess = _create_session(client)
    bad = _minimal_manifest()
    bad["action_mapping"] = {"mode": "raw_torque", "joints": []}
    response = client.post(
        f"/sessions/{sess['run_id']}/package",
        json=bad,
        headers=_bearer(sess["run_token"]),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "rejected"
    assert payload["errors"]


def test_malformed_payload_returns_422(client) -> None:
    sess = _create_session(client)
    response = client.post(
        f"/sessions/{sess['run_id']}/package",
        json={"name": "missing-everything"},
        headers=_bearer(sess["run_token"]),
    )
    assert response.status_code == 422


def test_session_state_transitions_on_validation(client, manager) -> None:
    sess = _create_session(client)
    client.post(
        f"/sessions/{sess['run_id']}/package",
        json=_minimal_manifest(),
        headers=_bearer(sess["run_token"]),
    )
    session = manager._sessions[sess["run_id"]]
    assert session.state.value == "package_validated"

    bad_sess = _create_session(client)
    bad = _minimal_manifest()
    bad["sensors"] = []
    client.post(
        f"/sessions/{bad_sess['run_id']}/package",
        json=bad,
        headers=_bearer(bad_sess["run_token"]),
    )
    bad_session = manager._sessions[bad_sess["run_id"]]
    assert bad_session.state.value == "package_rejected"

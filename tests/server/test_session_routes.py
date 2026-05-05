"""Session creation + status route tests."""

from __future__ import annotations

from .conftest import BOOTSTRAP_TOKEN


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_session_creation_requires_bootstrap_token(client) -> None:
    response = client.post("/sessions", json={})
    assert response.status_code == 401


def test_session_creation_with_wrong_bootstrap_token_rejected(client) -> None:
    response = client.post(
        "/sessions", json={}, headers=_bearer("wrong-token")
    )
    assert response.status_code == 401


def test_session_creation_returns_run_token(client) -> None:
    response = client.post(
        "/sessions",
        json={"participant_id": "alice"},
        headers=_bearer(BOOTSTRAP_TOKEN),
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["run_id"]
    assert len(payload["run_token"]) >= 32  # 128-bit floor as hex
    assert payload["state"] == "created"


def test_session_status_requires_run_token(client) -> None:
    create = client.post(
        "/sessions", json={}, headers=_bearer(BOOTSTRAP_TOKEN)
    ).json()
    run_id = create["run_id"]

    no_auth = client.get(f"/sessions/{run_id}")
    assert no_auth.status_code == 401

    wrong_auth = client.get(
        f"/sessions/{run_id}", headers=_bearer("wrong")
    )
    assert wrong_auth.status_code == 401


def test_session_status_with_run_token_returns_state(client) -> None:
    create = client.post(
        "/sessions", json={}, headers=_bearer(BOOTSTRAP_TOKEN)
    ).json()
    response = client.get(
        f"/sessions/{create['run_id']}", headers=_bearer(create["run_token"])
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == create["run_id"]
    assert payload["state"] == "created"
    assert payload["has_active_control_stream"] is False


def test_session_status_with_unknown_run_id_returns_404(client) -> None:
    response = client.get(
        "/sessions/does-not-exist", headers=_bearer("any-token")
    )
    assert response.status_code in {401, 404}


def test_loopback_bootstrap_disabled_in_config_under_test(client) -> None:
    """Even when the request comes from 127.0.0.1, the test config has
    loopback bootstrap disabled, so the token is required."""
    response = client.post("/sessions", json={})
    assert response.status_code == 401


def test_session_count_capped(client) -> None:
    """The configured max_sessions=4 must reject the fifth concurrent session."""
    headers = _bearer(BOOTSTRAP_TOKEN)
    for _ in range(4):
        response = client.post("/sessions", json={}, headers=headers)
        assert response.status_code == 201
    over = client.post("/sessions", json={}, headers=headers)
    assert over.status_code == 503


def test_run_tokens_are_unique(client) -> None:
    headers = _bearer(BOOTSTRAP_TOKEN)
    tokens = set()
    for _ in range(3):
        response = client.post("/sessions", json={}, headers=headers).json()
        tokens.add(response["run_token"])
    assert len(tokens) == 3

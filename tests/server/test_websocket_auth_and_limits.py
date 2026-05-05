"""WebSocket auth and limit tests against the default echo orchestrator."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from .conftest import BOOTSTRAP_TOKEN


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_session(client: TestClient) -> dict[str, str]:
    return client.post(
        "/sessions", json={}, headers=_bearer(BOOTSTRAP_TOKEN)
    ).json()


def test_websocket_requires_token(client: TestClient) -> None:
    sess = _create_session(client)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/sessions/{sess['run_id']}/control"):
            pass


def test_websocket_rejects_wrong_token(client: TestClient) -> None:
    sess = _create_session(client)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            f"/sessions/{sess['run_id']}/control?run_token=wrong"
        ):
            pass


def test_websocket_accepts_valid_token_and_echoes(client: TestClient) -> None:
    sess = _create_session(client)
    url = f"/sessions/{sess['run_id']}/control?run_token={sess['run_token']}"
    with client.websocket_connect(url) as ws:
        ws.send_text("hello")
        payload = ws.receive_json()
        assert payload == {"echo": "hello"}


def test_websocket_marks_active_stream(client: TestClient, manager) -> None:
    sess = _create_session(client)
    url = f"/sessions/{sess['run_id']}/control?run_token={sess['run_token']}"
    session = manager._sessions[sess["run_id"]]
    assert session.has_active_control_stream is False
    with client.websocket_connect(url) as ws:
        # Round-trip a message so the orchestrator has actually entered the loop.
        ws.send_text("ping")
        ws.receive_json()
        assert session.has_active_control_stream is True
    assert session.has_active_control_stream is False


def test_second_concurrent_websocket_rejected(client: TestClient) -> None:
    sess = _create_session(client)
    url = f"/sessions/{sess['run_id']}/control?run_token={sess['run_token']}"
    with client.websocket_connect(url) as ws_a:
        ws_a.send_text("hi")
        ws_a.receive_json()
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(url):
                pass


def test_oversized_message_recorded_as_invalid(client: TestClient, manager) -> None:
    sess = _create_session(client)
    session = manager._sessions[sess["run_id"]]
    url = f"/sessions/{sess['run_id']}/control?run_token={sess['run_token']}"
    big_payload = "x" * (manager.config.max_message_bytes + 1)
    with client.websocket_connect(url) as ws:
        ws.send_text(big_payload)
        warning = ws.receive_json()
        assert "error" in warning
    assert session.invalid_message_count >= 1


def test_too_many_invalid_messages_close_stream(client: TestClient, manager) -> None:
    sess = _create_session(client)
    url = f"/sessions/{sess['run_id']}/control?run_token={sess['run_token']}"
    big_payload = "x" * (manager.config.max_message_bytes + 1)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(url) as ws:
            for _ in range(manager.config.max_invalid_messages + 2):
                ws.send_text(big_payload)
                # The server may either send an error or close immediately.
                try:
                    ws.receive_json()
                except WebSocketDisconnect:
                    raise

from __future__ import annotations

import json

import pytest

from asimovbm_client.transport import (
    TransportConfig,
    WebSocketBenchmarkServer,
    _http_base,
    _ws_base,
)
from asimovbm_protocol import PROTOCOL_VERSION, ProtocolError, SessionBootstrap


class FakeSocket:
    def __init__(self, messages: list[dict[str, object] | str]):
        self.messages = list(messages)
        self.sent: list[dict[str, object]] = []
        self.closed = False

    def send(self, payload: str) -> None:
        self.sent.append(json.loads(payload))

    def recv(self, timeout: float | None = None) -> str:
        if not self.messages:
            raise TimeoutError("no messages queued")
        message = self.messages.pop(0)
        if isinstance(message, str):
            return message
        return json.dumps(message)

    def close(self) -> None:
        self.closed = True


def test_base_url_derivation_accepts_http_and_websocket_schemes() -> None:
    assert _http_base("http://localhost:8000") == "http://localhost:8000"
    assert _http_base("ws://localhost:8000") == "http://localhost:8000"
    assert _http_base("wss://bench.example.test") == "https://bench.example.test"

    assert _ws_base("http://localhost:8000") == "ws://localhost:8000"
    assert _ws_base("https://bench.example.test") == "wss://bench.example.test"
    assert _ws_base("ws://localhost:8000") == "ws://localhost:8000"


def test_connect_sends_bootstrap_and_requires_ack(monkeypatch: pytest.MonkeyPatch) -> None:
    socket = FakeSocket(
        [{"type": "bootstrap_ack", "data": {"protocol_version": PROTOCOL_VERSION}}]
    )
    opened_urls: list[str] = []

    def fake_connect(url: str, **kwargs):
        opened_urls.append(url)
        assert kwargs["max_size"] == 1234
        return socket

    monkeypatch.setattr("asimovbm_client.transport.ws_connect", fake_connect)

    transport = WebSocketBenchmarkServer(
        TransportConfig(
            server_url="http://localhost:8000",
            run_id="run-1",
            run_token="token-1",
            max_message_bytes=1234,
        )
    )
    transport.connect(SessionBootstrap("token-1", participant_id="p1"))

    assert opened_urls == [
        "ws://localhost:8000/sessions/run-1/control?run_token=token-1"
    ]
    assert socket.sent[0]["type"] == "bootstrap"
    assert socket.sent[0]["data"]["participant_id"] == "p1"


def test_unexpected_control_message_maps_to_protocol_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    socket = FakeSocket(
        [
            {"type": "bootstrap_ack", "data": {"protocol_version": PROTOCOL_VERSION}},
            {"type": "action_rejected", "step_id": 7, "reason": "stale step"},
        ]
    )
    monkeypatch.setattr("asimovbm_client.transport.ws_connect", lambda *_, **__: socket)
    transport = WebSocketBenchmarkServer(
        TransportConfig("http://localhost:8000", run_id="run-1", run_token="token-1")
    )

    transport.connect(SessionBootstrap("token-1"))

    with pytest.raises(ProtocolError, match="stale step"):
        transport.next_step()


def test_malformed_server_message_maps_to_protocol_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    socket = FakeSocket(
        [
            {"type": "bootstrap_ack", "data": {"protocol_version": PROTOCOL_VERSION}},
            "not json",
        ]
    )
    monkeypatch.setattr("asimovbm_client.transport.ws_connect", lambda *_, **__: socket)
    transport = WebSocketBenchmarkServer(
        TransportConfig("http://localhost:8000", run_id="run-1", run_token="token-1")
    )

    transport.connect(SessionBootstrap("token-1"))

    with pytest.raises(ProtocolError, match="malformed server message"):
        transport.next_step()

"""Real benchmark client transport.

Implements the :class:`asimovbm_client.runner.core.BenchmarkServer` Protocol
over a network connection to ``asimovbm_server``:

- HTTP is used for session bootstrap (POST /sessions when the caller does
  not already hold a run token) and package validation
  (POST /sessions/{run_id}/package).
- WebSocket carries the control loop (bootstrap message, step/action
  exchange, terminal message).

The runner sees a single object satisfying the existing protocol, so
``StepSynchronousRunner`` works against the fake in-process backend or the
real server with no additional changes.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect as ws_connect

from asimovbm_protocol import (
    ActionMessage,
    FailureMessage,
    PackageSubmission,
    ProtocolError,
    SessionBootstrap,
    StepMessage,
    TerminalMessage,
    to_payload,
)
from asimovbm_protocol.adapters import (
    package_submission_adapter,
    step_message_adapter,
    terminal_message_adapter,
    validation_response_adapter,
)

logger = logging.getLogger(__name__)


@dataclass
class TransportConfig:
    """Network transport configuration.

    ``server_url`` may be ``http(s)://`` or ``ws(s)://``. The schemes are
    derived for HTTP and WebSocket independently from the base.
    ``run_id`` and ``run_token`` may be supplied directly when the caller
    already holds a token; otherwise ``bootstrap_token`` lets the transport
    create a fresh session through the admin route.
    """

    server_url: str
    run_token: str | None = None
    run_id: str | None = None
    bootstrap_token: str | None = None
    receive_timeout_s: float = 10.0
    max_message_bytes: int = 1_048_576


class TransportError(RuntimeError):
    pass


class DisconnectError(TransportError):
    pass


def _http_base(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme in {"https", "wss"}:
        scheme = "https"
    elif parsed.scheme in {"http", "ws"}:
        scheme = "http"
    else:
        scheme = "http"
    netloc = parsed.netloc or url
    return f"{scheme}://{netloc}"


def _ws_base(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme in {"https", "wss"}:
        scheme = "wss"
    else:
        scheme = "ws"
    netloc = parsed.netloc or url
    return f"{scheme}://{netloc}"


class WebSocketBenchmarkServer:
    """Network-backed benchmark server adapter for the client runner."""

    def __init__(self, config: TransportConfig):
        self._config = config
        self._http = _http_base(config.server_url)
        self._ws_url_base = _ws_base(config.server_url)
        self._run_id = config.run_id
        self._run_token = config.run_token
        self._ws = None
        self._terminal_seen = False

    # --- BenchmarkServer Protocol -------------------------------------

    def connect(self, bootstrap: SessionBootstrap) -> None:
        if self._run_id is None or self._run_token is None:
            self._run_id, self._run_token = self._create_session(bootstrap)

        ws_url = (
            f"{self._ws_url_base}/sessions/{self._run_id}/control"
            f"?run_token={self._run_token}"
        )
        try:
            self._ws = ws_connect(
                ws_url,
                max_size=self._config.max_message_bytes,
                open_timeout=self._config.receive_timeout_s,
            )
        except (OSError, ConnectionClosed) as exc:
            raise ProtocolError(f"failed to open control stream: {exc}") from exc

        self._send({"type": "bootstrap", "data": to_payload(bootstrap)})
        ack = self._receive()
        if ack.get("type") == "error":
            raise ProtocolError(ack.get("summary", "server rejected bootstrap"))
        if ack.get("type") != "bootstrap_ack":
            raise ProtocolError(
                f"unexpected first server message: {ack.get('type')!r}"
            )
        ack_data = ack.get("data", {})
        if ack_data.get("protocol_version") != bootstrap.protocol_version:
            raise ProtocolError(
                "server protocol version mismatch: "
                f"client={bootstrap.protocol_version}, server={ack_data.get('protocol_version')}"
            )

    def submit_package(self, package: PackageSubmission):
        url = f"{self._http}/sessions/{self._run_id}/package"
        body = json.dumps(
            package_submission_adapter.dump_python(package, mode="json")
        ).encode("utf-8")
        request = Request(
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._run_token}",
            },
        )
        try:
            with urlopen(request, timeout=self._config.receive_timeout_s) as resp:
                payload = json.loads(resp.read())
        except HTTPError as exc:
            raise ProtocolError(
                f"package submission rejected with HTTP {exc.code}"
            ) from exc
        except URLError as exc:
            raise ProtocolError(f"package submission failed: {exc.reason}") from exc
        return validation_response_adapter.validate_python(payload)

    def next_step(self) -> StepMessage | TerminalMessage:
        if self._terminal_seen:
            raise ProtocolError("terminal state has already been received")
        msg = self._receive()
        kind = msg.get("type")
        if kind == "step":
            return step_message_adapter.validate_python(msg["data"])
        if kind == "terminal":
            self._terminal_seen = True
            return terminal_message_adapter.validate_python(msg["data"])
        if kind == "action_rejected":
            # Surface server-side rejection as a protocol-level signal that
            # the action was invalid. The runner will turn this into a
            # technical failure on the next step attempt.
            raise ProtocolError(
                f"server rejected action for step {msg.get('step_id')}: "
                f"{msg.get('reason')}"
            )
        raise ProtocolError(f"server returned unexpected message type: {kind!r}")

    def submit_action(self, action: ActionMessage) -> None:
        self._send({"type": "action", "data": to_payload(action)})

    def record_failure(self, failure: FailureMessage) -> None:
        if self._ws is None:
            return
        try:
            self._send({"type": "failure", "data": to_payload(failure)})
        except Exception:  # best-effort telemetry only
            pass

    def close(self) -> None:
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None

    # --- helpers -------------------------------------------------------

    def _create_session(self, bootstrap: SessionBootstrap) -> tuple[str, str]:
        if not self._config.bootstrap_token:
            raise ProtocolError(
                "run_id/run_token missing and no bootstrap_token provided to "
                "create a session"
            )
        url = f"{self._http}/sessions"
        body = json.dumps({"participant_id": bootstrap.participant_id}).encode("utf-8")
        request = Request(
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._config.bootstrap_token}",
            },
        )
        try:
            with urlopen(request, timeout=self._config.receive_timeout_s) as resp:
                payload = json.loads(resp.read())
        except HTTPError as exc:
            raise ProtocolError(
                f"session bootstrap rejected with HTTP {exc.code}"
            ) from exc
        except URLError as exc:
            raise ProtocolError(f"session bootstrap failed: {exc.reason}") from exc
        return payload["run_id"], payload["run_token"]

    def _send(self, message: dict[str, Any]) -> None:
        if self._ws is None:
            raise ProtocolError("control stream is not connected")
        try:
            self._ws.send(json.dumps(message))
        except (ConnectionClosed, OSError) as exc:
            raise DisconnectError(f"connection closed during send: {exc}") from exc

    def _receive(self) -> dict[str, Any]:
        if self._ws is None:
            raise ProtocolError("control stream is not connected")
        try:
            raw = self._ws.recv(timeout=self._config.receive_timeout_s)
        except TimeoutError:
            raise
        except (ConnectionClosed, OSError) as exc:
            raise DisconnectError(f"connection closed during receive: {exc}") from exc
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProtocolError(f"malformed server message: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ProtocolError("server message must be a JSON object")
        return parsed

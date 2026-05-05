"""Control-loop WebSocket route.

The route is responsible for token authentication, single-stream
enforcement, message-size limits, invalid-message accounting, and clean
disconnect handling. The actual episode lifecycle (step/action exchange)
is delegated to an :class:`EpisodeOrchestrator`. The default orchestrator
is a no-op shell so this unit's shape stays stable while the real
simulation wiring lands in later units.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Protocol

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect, status
from fastapi.websockets import WebSocketState

from ..sessions import (
    ControlStreamConflictError,
    Session,
    SessionAuthError,
    SessionManager,
    SessionNotFoundError,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class EpisodeOrchestrator(Protocol):
    """Drives the step/action exchange for a single control stream."""

    async def run(self, session: Session, websocket: WebSocket) -> None: ...


class EchoOrchestrator:
    """Default no-op orchestrator. Echoes every message back as ``{"echo": ...}``.

    Useful for transport-level tests; real orchestrators land in Unit 6.
    """

    async def run(self, session: Session, websocket: WebSocket) -> None:
        while websocket.client_state == WebSocketState.CONNECTED:
            try:
                payload = await websocket.receive_text()
            except WebSocketDisconnect:
                return
            await websocket.send_json({"echo": payload})


def _query_token(websocket: WebSocket) -> str | None:
    return websocket.query_params.get("run_token")


def _header_token(websocket: WebSocket) -> str | None:
    auth = websocket.headers.get("authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth[len("bearer ") :].strip()
    return None


@router.websocket("/sessions/{run_id}/control")
async def control_stream(websocket: WebSocket, run_id: str) -> None:
    request: Request = websocket  # type: ignore[assignment]
    manager: SessionManager = websocket.app.state.session_manager
    config = websocket.app.state.config
    orchestrator: EpisodeOrchestrator = websocket.app.state.orchestrator

    token = _header_token(websocket) or _query_token(websocket)
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        session = manager.authenticate(run_id, token)
    except SessionNotFoundError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    except SessionAuthError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        manager.open_control_stream(session)
    except ControlStreamConflictError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    try:
        await _run_with_limits(websocket, session, manager, config, orchestrator)
    finally:
        manager.close_control_stream(session)
        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                await websocket.close()
            except RuntimeError:
                pass


async def _run_with_limits(
    websocket: WebSocket,
    session: Session,
    manager: SessionManager,
    config,
    orchestrator: EpisodeOrchestrator,
) -> None:
    # Wrap the orchestrator with a guard that enforces message size and
    # invalid-message limits without forcing every orchestrator to know
    # about config.
    original_receive_text = websocket.receive_text
    original_receive_json = websocket.receive_json

    async def guarded_receive_text() -> str:
        text = await original_receive_text()
        if len(text.encode("utf-8")) > config.max_message_bytes:
            count = manager.record_invalid_message(session)
            if count >= config.max_invalid_messages:
                await websocket.close(code=status.WS_1009_MESSAGE_TOO_BIG)
                raise WebSocketDisconnect(code=status.WS_1009_MESSAGE_TOO_BIG)
            await websocket.send_json({"error": "message too large"})
            return await guarded_receive_text()
        return text

    async def guarded_receive_json() -> Any:
        text = await guarded_receive_text()
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            count = manager.record_invalid_message(session)
            if count >= config.max_invalid_messages:
                await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
                raise WebSocketDisconnect(code=status.WS_1003_UNSUPPORTED_DATA) from exc
            await websocket.send_json({"error": "malformed json"})
            return await guarded_receive_json()

    websocket.receive_text = guarded_receive_text  # type: ignore[assignment]
    websocket.receive_json = guarded_receive_json  # type: ignore[assignment]

    try:
        await orchestrator.run(session, websocket)
    except WebSocketDisconnect:
        return

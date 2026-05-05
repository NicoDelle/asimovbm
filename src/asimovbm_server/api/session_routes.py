"""Session creation and lookup routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..sessions import (
    SessionLimitError,
    SessionManager,
)
from .auth import (
    get_session_manager,
    require_bootstrap_token,
    require_run_token,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    participant_id: str | None = None


class CreateSessionResponse(BaseModel):
    run_id: str
    run_token: str
    state: str


class SessionStatusResponse(BaseModel):
    run_id: str
    state: str
    has_active_control_stream: bool
    report_ref: str | None
    invalid_message_count: int


@router.post("", response_model=CreateSessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: CreateSessionRequest,
    manager: Annotated[SessionManager, Depends(get_session_manager)],
    _: Annotated[None, Depends(require_bootstrap_token)],
) -> CreateSessionResponse:
    try:
        session = manager.create_session(participant_id=payload.participant_id)
    except SessionLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="session limit reached",
        ) from exc
    return CreateSessionResponse(
        run_id=session.run_id,
        run_token=session.run_token,
        state=session.state.value,
    )


@router.get("/{run_id}", response_model=SessionStatusResponse)
def session_status(run_id: str, session=Depends(require_run_token)) -> SessionStatusResponse:
    return SessionStatusResponse(
        run_id=session.run_id,
        state=session.state.value,
        has_active_control_stream=session.has_active_control_stream,
        report_ref=session.report_ref,
        invalid_message_count=session.invalid_message_count,
    )

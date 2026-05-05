"""Token authentication helpers for FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status

from ..sessions import (
    Session,
    SessionAuthError,
    SessionManager,
    SessionNotFoundError,
)


def get_session_manager(request: Request) -> SessionManager:
    manager: SessionManager | None = getattr(request.app.state, "session_manager", None)
    if manager is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="session manager not configured",
        )
    return manager


def _extract_bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token"
        )
    return authorization[len("bearer ") :].strip()


def require_bootstrap_token(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    config = request.app.state.config
    if (
        config.allow_loopback_session_creation
        and request.client is not None
        and request.client.host in {"127.0.0.1", "::1", "localhost"}
        and not authorization
    ):
        return
    token = _extract_bearer(authorization)
    expected = config.bootstrap_token
    # Constant-time compare via the same primitive used for run tokens.
    from ..sessions import _constant_time_equals  # local import to avoid cycle in docs

    if not _constant_time_equals(token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid bootstrap token"
        )


def require_run_token(
    run_id: str,
    authorization: Annotated[str | None, Header()] = None,
    manager: SessionManager = Depends(get_session_manager),
) -> Session:
    token = _extract_bearer(authorization)
    try:
        return manager.authenticate(run_id, token)
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="session not found"
        ) from exc
    except SessionAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid run token"
        ) from exc


def require_run_token_for_report(
    report_ref: str,
    authorization: Annotated[str | None, Header()] = None,
    manager: SessionManager = Depends(get_session_manager),
) -> Session:
    token = _extract_bearer(authorization)
    try:
        return manager.authenticate_by_report_ref(report_ref, token)
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="report not found"
        ) from exc
    except SessionAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid run token"
        ) from exc

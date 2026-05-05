"""Report retrieval routes.

The report ref is opaque. The route looks the ref up in the session
manager's report index, requires the matching run token, and returns the
in-memory report payload. Filesystem paths are never exposed.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..sessions import Session, SessionManager
from .auth import get_session_manager, require_run_token_for_report

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/{report_ref:path}")
def get_report(
    report_ref: str,
    request: Request,
    session: Annotated[Session, Depends(require_run_token_for_report)],
    manager: Annotated[SessionManager, Depends(get_session_manager)],
) -> dict[str, Any]:
    reports: dict[str, dict[str, Any]] = getattr(request.app.state, "reports", {})
    if report_ref not in reports:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="report not found"
        )
    if session.report_ref != report_ref:
        # Defense in depth: the auth dependency already matched the ref to
        # the session, but we re-check to ensure no caller can swap refs.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="report does not belong to session"
        )
    return reports[report_ref]

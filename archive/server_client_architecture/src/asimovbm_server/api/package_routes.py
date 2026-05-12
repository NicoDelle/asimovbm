"""Package submission and validation routes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import ValidationError

from asimovbm_protocol import PackageSubmission
from asimovbm_protocol.adapters import (
    package_submission_adapter,
    validation_response_adapter,
)

from ..packages import validate_remote_manifest
from ..sessions import Session, SessionManager
from .auth import get_session_manager, require_run_token

router = APIRouter(prefix="/sessions", tags=["packages"])


@router.post("/{run_id}/package")
def submit_package(
    run_id: str,
    payload: Annotated[dict[str, Any], Body(...)],
    session: Annotated[Session, Depends(require_run_token)],
    manager: Annotated[SessionManager, Depends(get_session_manager)],
) -> dict[str, Any]:
    try:
        submission: PackageSubmission = package_submission_adapter.validate_python(payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors(),
        ) from exc

    result = validate_remote_manifest(
        submission, server_settings={"control_dt": 0.025}
    )
    response = result.to_response()
    manager.attach_package(session, submission, response)
    return validation_response_adapter.dump_python(response, mode="json")

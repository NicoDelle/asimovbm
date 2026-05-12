"""Asimov benchmark server."""

from __future__ import annotations

from .config import ServerConfig, generate_token
from .sessions import (
    ControlStreamConflictError,
    Session,
    SessionAuthError,
    SessionLimitError,
    SessionManager,
    SessionNotFoundError,
    SessionState,
)

def __getattr__(name: str):
    if name == "create_app":
        from .app import create_app

        return create_app
    raise AttributeError(name)


__all__ = [
    "ControlStreamConflictError",
    "ServerConfig",
    "Session",
    "SessionAuthError",
    "SessionLimitError",
    "SessionManager",
    "SessionNotFoundError",
    "SessionState",
    "create_app",
    "generate_token",
]

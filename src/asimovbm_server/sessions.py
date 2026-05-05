"""In-memory session manager.

Owns run tokens, session state, package validation results, report refs, and
control-stream registration. Storage is process-memory for MVP; persistence,
multi-worker coordination, and TLS termination are deferred.
"""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from asimovbm_protocol import PackageSubmission, ValidationResponse

from .config import ServerConfig, generate_token


class SessionState(StrEnum):
    CREATED = "created"
    BOOTSTRAPPED = "bootstrapped"
    PACKAGE_VALIDATED = "package_validated"
    PACKAGE_REJECTED = "package_rejected"
    RUNNING = "running"
    TERMINAL = "terminal"
    EXPIRED = "expired"


@dataclass
class Session:
    run_id: str
    run_token: str
    participant_id: str | None
    created_at: float
    state: SessionState = SessionState.CREATED
    package: PackageSubmission | None = None
    validation: ValidationResponse | None = None
    report_ref: str | None = None
    invalid_message_count: int = 0
    has_active_control_stream: bool = False
    artifact_dir: Path | None = None
    last_activity: float = field(default_factory=time.monotonic)
    terminal_at: float | None = None

    def touch(self) -> None:
        self.last_activity = time.monotonic()


class SessionLimitError(RuntimeError):
    """Raised when the configured session ceiling has been reached."""


class SessionAuthError(RuntimeError):
    """Raised when token authentication fails."""


class SessionNotFoundError(KeyError):
    """Raised when a referenced session no longer exists."""


class ControlStreamConflictError(RuntimeError):
    """Raised when a second control stream is opened for the same session."""


class SessionManager:
    """Thread-safe in-memory session store.

    Run tokens are compared with :func:`secrets.compare_digest` to avoid
    timing oracles. The run token never appears in returned diagnostics or
    log messages — callers receive only the public ``run_id``.
    """

    def __init__(self, config: ServerConfig):
        self.config = config
        self._sessions: dict[str, Session] = {}
        self._token_index: dict[str, str] = {}  # token -> run_id
        self._report_index: dict[str, str] = {}  # report_ref -> run_id
        self._lock = threading.RLock()

    # ----- creation / lookup --------------------------------------------

    def create_session(self, *, participant_id: str | None = None) -> Session:
        with self._lock:
            self._reap_expired_locked()
            if len(self._sessions) >= self.config.max_sessions:
                raise SessionLimitError("session limit reached")
            run_id = secrets.token_hex(8)
            run_token = generate_token()
            artifact_dir = self.config.artifact_root / run_id
            artifact_dir.mkdir(parents=True, exist_ok=True)
            try:
                artifact_dir.chmod(0o700)
            except OSError:
                # Permission tightening is best-effort across platforms.
                pass
            session = Session(
                run_id=run_id,
                run_token=run_token,
                participant_id=participant_id,
                created_at=time.time(),
                artifact_dir=artifact_dir,
            )
            self._sessions[run_id] = session
            self._token_index[run_token] = run_id
            return session

    def authenticate(self, run_id: str, presented_token: str) -> Session:
        """Return the session matching ``run_id``/token or raise.

        ``presented_token`` is compared with :func:`secrets.compare_digest`
        so attackers cannot use timing differences to brute-force the token.
        """
        with self._lock:
            session = self._sessions.get(run_id)
            if session is None:
                raise SessionNotFoundError(run_id)
            if not _constant_time_equals(session.run_token, presented_token):
                raise SessionAuthError("invalid token")
            self._check_not_expired_locked(session)
            session.touch()
            return session

    def authenticate_by_token(self, presented_token: str) -> Session:
        """Look up a session purely by token. Avoids leaking run_id state."""
        with self._lock:
            run_id = self._token_index.get(presented_token)
            if run_id is None:
                raise SessionAuthError("invalid token")
            return self.authenticate(run_id, presented_token)

    def authenticate_by_report_ref(self, report_ref: str, presented_token: str) -> Session:
        with self._lock:
            run_id = self._report_index.get(report_ref)
            if run_id is None:
                raise SessionNotFoundError(report_ref)
            return self.authenticate(run_id, presented_token)

    # ----- lifecycle transitions ---------------------------------------

    def attach_package(
        self,
        session: Session,
        package: PackageSubmission,
        validation: ValidationResponse,
    ) -> None:
        with self._lock:
            session.package = package
            session.validation = validation
            session.state = (
                SessionState.PACKAGE_VALIDATED
                if validation.accepted
                else SessionState.PACKAGE_REJECTED
            )
            session.touch()

    def open_control_stream(self, session: Session) -> None:
        with self._lock:
            if session.has_active_control_stream:
                raise ControlStreamConflictError("already has an active control stream")
            session.has_active_control_stream = True
            session.state = SessionState.RUNNING
            session.touch()

    def close_control_stream(self, session: Session) -> None:
        with self._lock:
            session.has_active_control_stream = False
            session.touch()

    def record_invalid_message(self, session: Session) -> int:
        with self._lock:
            session.invalid_message_count += 1
            session.touch()
            return session.invalid_message_count

    def finalize(self, session: Session, *, report_ref: str) -> None:
        """Move the session to TERMINAL and register the opaque report ref."""
        with self._lock:
            session.state = SessionState.TERMINAL
            session.report_ref = report_ref
            session.terminal_at = time.monotonic()
            session.has_active_control_stream = False
            self._report_index[report_ref] = session.run_id
            session.touch()

    def remove(self, session: Session) -> None:
        with self._lock:
            self._sessions.pop(session.run_id, None)
            self._token_index.pop(session.run_token, None)
            if session.report_ref is not None:
                self._report_index.pop(session.report_ref, None)

    # ----- internals ----------------------------------------------------

    def _check_not_expired_locked(self, session: Session) -> None:
        now = time.monotonic()
        if session.state == SessionState.TERMINAL:
            assert session.terminal_at is not None
            if now - session.terminal_at > self.config.terminal_grace_s:
                session.state = SessionState.EXPIRED
                raise SessionAuthError("session expired")
            return
        if now - session.last_activity > self.config.session_idle_timeout_s:
            session.state = SessionState.EXPIRED
            raise SessionAuthError("session expired")

    def _reap_expired_locked(self) -> None:
        now = time.monotonic()
        expired: list[str] = []
        for run_id, session in self._sessions.items():
            if session.state == SessionState.TERMINAL:
                if (
                    session.terminal_at is not None
                    and now - session.terminal_at > self.config.terminal_grace_s
                ):
                    expired.append(run_id)
            elif now - session.last_activity > self.config.session_idle_timeout_s:
                expired.append(run_id)
        for run_id in expired:
            session = self._sessions.pop(run_id, None)
            if session is None:
                continue
            self._token_index.pop(session.run_token, None)
            if session.report_ref is not None:
                self._report_index.pop(session.report_ref, None)

    # ----- report helpers ----------------------------------------------

    def make_report_ref(self) -> str:
        """Return a fresh opaque report reference. No filesystem path is
        embedded so the ref cannot leak deployment internals."""
        return f"srv://reports/{secrets.token_hex(16)}"


def _constant_time_equals(a: str, b: str) -> bool:
    return secrets.compare_digest(a.encode("utf-8"), b.encode("utf-8"))

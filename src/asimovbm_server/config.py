"""Server configuration.

Configuration is intentionally explicit. All security-relevant defaults are
conservative: the bootstrap token must be supplied at startup; sessions
expire; per-message and per-session limits are bounded.
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ServerConfig:
    bootstrap_token: str
    """Admin/bootstrap token. Required to create new sessions through the
    HTTP session creation route. Distinct from per-run tokens."""

    artifact_root: Path
    """Directory for per-run artifact output. Each run gets its own
    sub-directory with restrictive permissions."""

    fixture_roots: dict[str, Path] = field(default_factory=dict)
    """Optional named fixture directories for server-local package mode.
    Keys are fixture identifiers, values are absolute fixture paths."""

    max_sessions: int = 64
    """Maximum concurrent in-memory sessions before the server rejects
    further session creation."""

    max_message_bytes: int = 1_048_576  # 1 MiB
    """Maximum size for a single WebSocket message. Oversized messages are
    recorded as a technical failure and the connection is closed."""

    max_invalid_messages: int = 8
    """Maximum number of malformed/invalid control messages allowed before
    the server closes the connection as a technical failure."""

    session_idle_timeout_s: float = 300.0
    """Seconds of WebSocket inactivity before the server treats the session
    as disconnected."""

    terminal_grace_s: float = 600.0
    """Seconds after terminal state during which the run token can still
    retrieve the final report. After this window the session and any
    artifacts may be reclaimed."""

    allow_loopback_session_creation: bool = True
    """If true, the development bootstrap endpoint accepts requests from
    127.0.0.1 without the bootstrap token. Disable in production."""

    @classmethod
    def from_env(cls, *, artifact_root: Path | None = None) -> "ServerConfig":
        """Build config from environment variables. Used by the CLI launcher."""
        bootstrap = os.environ.get("ASIMOVBM_BOOTSTRAP_TOKEN")
        if not bootstrap:
            bootstrap = generate_token()
        root = artifact_root or Path(
            os.environ.get("ASIMOVBM_ARTIFACT_ROOT", "./artifacts")
        )
        return cls(bootstrap_token=bootstrap, artifact_root=root)


def generate_token(num_bytes: int = 32) -> str:
    """Return a hex token with at least 128 bits of entropy.

    Uses :func:`secrets.token_hex` which draws from the OS CSPRNG. The
    default of 32 bytes (256 bits) comfortably exceeds the 128-bit floor
    documented in the security plan.
    """
    if num_bytes < 16:
        raise ValueError("Run tokens must use at least 128 bits of entropy")
    return secrets.token_hex(num_bytes)

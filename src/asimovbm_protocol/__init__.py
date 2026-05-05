"""Shared benchmark client/server message contract.

The dataclasses in :mod:`asimovbm_protocol.models` are the single source of
truth for the on-the-wire message lifecycle. They are re-exported from
``asimovbm_client.protocol`` for backwards compatibility.

Use :mod:`asimovbm_protocol.adapters` for runtime validation at external
boundaries (HTTP/WebSocket payloads). Use :mod:`asimovbm_protocol.schema` for
JSON Schema generation.
"""

from __future__ import annotations

from .models import (
    PROTOCOL_VERSION,
    ActionMessage,
    ClientCapabilities,
    FailureCategory,
    FailureMessage,
    PackageSubmission,
    ProtocolError,
    SensorReading,
    SessionBootstrap,
    StepMessage,
    TaskEvent,
    TerminalMessage,
    TerminalStatus,
    ValidationResponse,
    ValidationStatus,
    to_payload,
)

__all__ = [
    "ActionMessage",
    "ClientCapabilities",
    "FailureCategory",
    "FailureMessage",
    "PROTOCOL_VERSION",
    "PackageSubmission",
    "ProtocolError",
    "SensorReading",
    "SessionBootstrap",
    "StepMessage",
    "TaskEvent",
    "TerminalMessage",
    "TerminalStatus",
    "ValidationResponse",
    "ValidationStatus",
    "to_payload",
]

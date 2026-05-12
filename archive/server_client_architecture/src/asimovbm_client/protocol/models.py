"""Backwards-compatible re-export of the shared protocol models.

The real source of truth lives in :mod:`asimovbm_protocol.models`. This shim
keeps existing ``from asimovbm_client.protocol.models import ...`` imports
working unchanged.
"""

from __future__ import annotations

from asimovbm_protocol.models import (
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

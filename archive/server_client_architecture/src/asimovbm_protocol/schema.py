"""JSON Schema export for the shared protocol.

Schemas are derived from the Pydantic ``TypeAdapter`` instances in
:mod:`asimovbm_protocol.adapters`. Server documentation, client-side
contract checks, and external integrators can use these without importing
runtime validation machinery directly.
"""

from __future__ import annotations

from typing import Any

from .adapters import ADAPTERS
from .models import (
    PROTOCOL_VERSION,
    FailureCategory,
    TerminalStatus,
    ValidationStatus,
)

PUBLIC_MESSAGE_NAMES: tuple[str, ...] = (
    "SessionBootstrap",
    "ClientCapabilities",
    "PackageSubmission",
    "ValidationResponse",
    "SensorReading",
    "TaskEvent",
    "StepMessage",
    "ActionMessage",
    "FailureMessage",
    "TerminalMessage",
)

PUBLIC_ENUMS: tuple[type, ...] = (
    ValidationStatus,
    TerminalStatus,
    FailureCategory,
)


def message_schema(name: str) -> dict[str, Any]:
    """Return the JSON Schema for a single named message."""
    if name not in ADAPTERS:
        raise KeyError(f"Unknown protocol message: {name}")
    return ADAPTERS[name].json_schema()


def export_protocol_schema() -> dict[str, Any]:
    """Return the full protocol schema bundle.

    The bundle includes the protocol version, every public message schema,
    and the enum members. Field names match the dataclass definitions and are
    stable across the v0 contract.
    """
    return {
        "protocol_version": PROTOCOL_VERSION,
        "messages": {name: message_schema(name) for name in PUBLIC_MESSAGE_NAMES},
        "enums": {
            enum_cls.__name__: [member.value for member in enum_cls]
            for enum_cls in PUBLIC_ENUMS
        },
    }


__all__ = [
    "PUBLIC_ENUMS",
    "PUBLIC_MESSAGE_NAMES",
    "export_protocol_schema",
    "message_schema",
]

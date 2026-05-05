"""Transport-neutral benchmark client protocol models."""

from .fake import FakeBenchmarkServer, FakeServerScript
from .models import (
    ActionMessage,
    ClientCapabilities,
    FailureCategory,
    FailureMessage,
    PackageSubmission,
    PROTOCOL_VERSION,
    ProtocolError,
    SensorReading,
    SessionBootstrap,
    TaskEvent,
    TerminalMessage,
    TerminalStatus,
    ValidationResponse,
    ValidationStatus,
    StepMessage,
)

__all__ = [
    "ActionMessage",
    "ClientCapabilities",
    "FailureCategory",
    "FailureMessage",
    "FakeBenchmarkServer",
    "FakeServerScript",
    "PackageSubmission",
    "PROTOCOL_VERSION",
    "ProtocolError",
    "SensorReading",
    "SessionBootstrap",
    "StepMessage",
    "TaskEvent",
    "TerminalMessage",
    "TerminalStatus",
    "ValidationResponse",
    "ValidationStatus",
]

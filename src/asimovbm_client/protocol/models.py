from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


PROTOCOL_VERSION = "asimovbm.client.v0"


class ProtocolError(RuntimeError):
    """Raised when the local client and server protocol lifecycle diverge."""


class ValidationStatus(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class TerminalStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    INVALID = "invalid"
    REPORT_READY = "report_ready"


class FailureCategory(StrEnum):
    SETUP = "setup"
    PACKAGE_LOCAL_CHECK = "package_local_check"
    SERVER_VALIDATION = "server_validation"
    POLICY_EXCEPTION = "policy_exception"
    TRANSFORMER_EXCEPTION = "transformer_exception"
    INVALID_ACTION = "invalid_action"
    TIMEOUT = "timeout"
    DISCONNECT = "disconnect"
    COMPATIBILITY = "compatibility"


@dataclass(frozen=True)
class ClientCapabilities:
    policy_runtime: str = "python"
    supports_task_events: bool = True
    supports_sensor_freshness: bool = True
    supports_invalid_action_telemetry: bool = True


@dataclass(frozen=True)
class SessionBootstrap:
    run_token: str
    participant_id: str | None = None
    protocol_version: str = PROTOCOL_VERSION
    capabilities: ClientCapabilities = field(default_factory=ClientCapabilities)


@dataclass(frozen=True)
class SensorReading:
    name: str
    kind: str
    data: Any
    units: str | None = None
    fresh: bool = True
    timestamp: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TaskEvent:
    name: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PackageSubmission:
    name: str
    model: dict[str, Any]
    sensors: list[dict[str, Any]]
    action_mapping: dict[str, Any]
    robot_metadata: dict[str, Any] = field(default_factory=dict)
    visual_assets: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class ValidationResponse:
    status: ValidationStatus
    errors: list[str] = field(default_factory=list)
    settings: dict[str, Any] = field(default_factory=dict)

    @property
    def accepted(self) -> bool:
        return self.status == ValidationStatus.ACCEPTED


@dataclass(frozen=True)
class StepMessage:
    step_id: int
    sim_time: float
    control_dt: float
    sensors: list[SensorReading]
    task_events: list[TaskEvent] = field(default_factory=list)


@dataclass(frozen=True)
class ActionMessage:
    step_id: int
    action: list[float]
    latency_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    invalid_reason: str | None = None

    @property
    def valid(self) -> bool:
        return self.invalid_reason is None


@dataclass(frozen=True)
class FailureMessage:
    category: FailureCategory
    summary: str
    step_id: int | None = None
    retry_count: int = 0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TerminalMessage:
    status: TerminalStatus
    report_ref: str | None = None
    summary: str | None = None
    failures: list[FailureMessage] = field(default_factory=list)


def to_payload(message: Any) -> dict[str, Any]:
    """Return a JSON-like dictionary for docs, tests, and simple transports."""

    return asdict(message)

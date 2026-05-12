"""Pydantic v2 TypeAdapters for runtime validation at external boundaries.

The protocol dataclasses in :mod:`asimovbm_protocol.models` stay pure stdlib so
the client keeps a zero-dependency surface. This module wraps them with
Pydantic v2 ``TypeAdapter`` instances for use at HTTP/WebSocket boundaries
where untrusted JSON must be validated and coerced into typed messages.

Usage::

    from asimovbm_protocol.adapters import action_message_adapter

    msg = action_message_adapter.validate_python(json_dict)
    payload = action_message_adapter.dump_python(msg)
"""

from __future__ import annotations

from typing import Any

from pydantic import TypeAdapter

from .models import (
    ActionMessage,
    ClientCapabilities,
    FailureMessage,
    PackageSubmission,
    SensorReading,
    SessionBootstrap,
    StepMessage,
    TaskEvent,
    TerminalMessage,
    ValidationResponse,
)

session_bootstrap_adapter: TypeAdapter[SessionBootstrap] = TypeAdapter(SessionBootstrap)
client_capabilities_adapter: TypeAdapter[ClientCapabilities] = TypeAdapter(ClientCapabilities)
package_submission_adapter: TypeAdapter[PackageSubmission] = TypeAdapter(PackageSubmission)
validation_response_adapter: TypeAdapter[ValidationResponse] = TypeAdapter(ValidationResponse)
sensor_reading_adapter: TypeAdapter[SensorReading] = TypeAdapter(SensorReading)
task_event_adapter: TypeAdapter[TaskEvent] = TypeAdapter(TaskEvent)
step_message_adapter: TypeAdapter[StepMessage] = TypeAdapter(StepMessage)
action_message_adapter: TypeAdapter[ActionMessage] = TypeAdapter(ActionMessage)
failure_message_adapter: TypeAdapter[FailureMessage] = TypeAdapter(FailureMessage)
terminal_message_adapter: TypeAdapter[TerminalMessage] = TypeAdapter(TerminalMessage)

ADAPTERS: dict[str, TypeAdapter[Any]] = {
    "SessionBootstrap": session_bootstrap_adapter,
    "ClientCapabilities": client_capabilities_adapter,
    "PackageSubmission": package_submission_adapter,
    "ValidationResponse": validation_response_adapter,
    "SensorReading": sensor_reading_adapter,
    "TaskEvent": task_event_adapter,
    "StepMessage": step_message_adapter,
    "ActionMessage": action_message_adapter,
    "FailureMessage": failure_message_adapter,
    "TerminalMessage": terminal_message_adapter,
}

__all__ = [
    "ADAPTERS",
    "action_message_adapter",
    "client_capabilities_adapter",
    "failure_message_adapter",
    "package_submission_adapter",
    "sensor_reading_adapter",
    "session_bootstrap_adapter",
    "step_message_adapter",
    "task_event_adapter",
    "terminal_message_adapter",
    "validation_response_adapter",
]

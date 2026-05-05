from __future__ import annotations

from dataclasses import dataclass, field

from .models import (
    ActionMessage,
    FailureCategory,
    FailureMessage,
    PackageSubmission,
    PROTOCOL_VERSION,
    ProtocolError,
    SessionBootstrap,
    StepMessage,
    TerminalMessage,
    TerminalStatus,
    ValidationResponse,
    ValidationStatus,
)


@dataclass
class FakeServerScript:
    steps: list[StepMessage]
    validation_errors: list[str] = field(default_factory=list)
    supported_protocol_version: str = PROTOCOL_VERSION
    terminal_status: TerminalStatus = TerminalStatus.COMPLETED
    report_ref: str = "fake://reports/run-001"
    fail_once_on_step: int | None = None


class FakeBenchmarkServer:
    """Executable server contract for local client tests.

    The fake validates lifecycle order and records telemetry. It deliberately
    does not simulate, score, render, or validate package physics.
    """

    def __init__(self, script: FakeServerScript):
        self.script = script
        self.bootstrap: SessionBootstrap | None = None
        self.package: PackageSubmission | None = None
        self.actions: list[ActionMessage] = []
        self.failures: list[FailureMessage] = []
        self._validated = False
        self._next_step_index = 0
        self._failed_once = False

    def connect(self, bootstrap: SessionBootstrap) -> None:
        if bootstrap.protocol_version != self.script.supported_protocol_version:
            raise ProtocolError(
                "Unsupported protocol version "
                f"{bootstrap.protocol_version}; expected {self.script.supported_protocol_version}"
            )
        self.bootstrap = bootstrap

    def submit_package(self, package: PackageSubmission) -> ValidationResponse:
        self._require_connected()
        self.package = package
        self._validated = True
        if self.script.validation_errors:
            return ValidationResponse(
                ValidationStatus.REJECTED,
                errors=list(self.script.validation_errors),
            )
        return ValidationResponse(
            ValidationStatus.ACCEPTED,
            settings={"control_dt": self.script.steps[0].control_dt if self.script.steps else 0.025},
        )

    def next_step(self) -> StepMessage | TerminalMessage:
        self._require_validated()
        if self._next_step_index >= len(self.script.steps):
            return TerminalMessage(
                self.script.terminal_status,
                report_ref=self.script.report_ref,
                failures=list(self.failures),
            )

        step = self.script.steps[self._next_step_index]
        if (
            self.script.fail_once_on_step == step.step_id
            and not self._failed_once
        ):
            self._failed_once = True
            raise TimeoutError(f"Transient fake timeout at step {step.step_id}")

        self._next_step_index += 1
        return step

    def submit_action(self, action: ActionMessage) -> None:
        self._require_validated()
        if not action.valid:
            self.failures.append(
                FailureMessage(
                    FailureCategory.INVALID_ACTION,
                    action.invalid_reason or "invalid action",
                    step_id=action.step_id,
                    details={"action": action.action},
                )
            )
        self.actions.append(action)

    def record_failure(self, failure: FailureMessage) -> None:
        self.failures.append(failure)

    def _require_connected(self) -> None:
        if self.bootstrap is None:
            raise ProtocolError("Session bootstrap must be sent before package submission")

    def _require_validated(self) -> None:
        self._require_connected()
        if not self._validated:
            raise ProtocolError("Package validation must complete before the control loop")

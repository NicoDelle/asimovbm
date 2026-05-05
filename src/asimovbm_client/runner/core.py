from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Protocol

from asimovbm_client.protocol import (
    ActionMessage,
    FailureCategory,
    FailureMessage,
    PackageSubmission,
    ProtocolError,
    SessionBootstrap,
    StepMessage,
    TerminalMessage,
    TerminalStatus,
    ValidationResponse,
    ValidationStatus,
)
from asimovbm_client.telemetry import redact_text


def _disconnect_error_class() -> type[Exception]:
    """Resolve transport.DisconnectError lazily to avoid an import cycle.

    The transport module imports from this module, so a top-level import of
    ``DisconnectError`` here would be circular. We resolve it once on first
    use and fall back to ``ConnectionError`` if the transport extra is not
    installed (in which case the runner only ever sees the fake backend).
    """
    try:
        from asimovbm_client.transport import DisconnectError

        return DisconnectError
    except Exception:  # pragma: no cover - websockets extra not installed
        return ConnectionError


_DisconnectErrorClass = _disconnect_error_class()


class BenchmarkServer(Protocol):
    def connect(self, bootstrap: SessionBootstrap) -> None: ...
    def submit_package(self, package: PackageSubmission) -> ValidationResponse: ...
    def next_step(self) -> StepMessage | TerminalMessage: ...
    def submit_action(self, action: ActionMessage) -> None: ...
    def record_failure(self, failure: FailureMessage) -> None: ...


@dataclass(frozen=True)
class RunnerConfig:
    run_token: str
    action_size: int
    participant_id: str | None = None
    retry_timeouts: int = 1


@dataclass
class ClientRunResult:
    terminal: TerminalMessage | None
    failures: list[FailureMessage] = field(default_factory=list)
    telemetry: list[FailureMessage] = field(default_factory=list)
    steps_completed: int = 0
    actions_sent: int = 0

    @property
    def ok(self) -> bool:
        return (
            self.terminal is not None
            and self.terminal.status in {TerminalStatus.COMPLETED, TerminalStatus.REPORT_READY}
            and not self.failures
        )


class StepSynchronousRunner:
    def __init__(
        self,
        server: BenchmarkServer,
        package: PackageSubmission,
        transformer,
        policy,
        config: RunnerConfig,
    ):
        self.server = server
        self.package = package
        self.transformer = transformer
        self.policy = policy
        self.config = config

    def run(self) -> ClientRunResult:
        result = ClientRunResult(terminal=None)
        try:
            self.server.connect(
                SessionBootstrap(
                    run_token=self.config.run_token,
                    participant_id=self.config.participant_id,
                )
            )
        except ProtocolError as exc:
            failure = FailureMessage(FailureCategory.COMPATIBILITY, str(exc))
            self.server.record_failure(failure)
            result.failures.append(failure)
            return result

        validation = self.server.submit_package(self.package)
        if validation.status != ValidationStatus.ACCEPTED:
            failure = FailureMessage(
                FailureCategory.SERVER_VALIDATION,
                "; ".join(validation.errors) or "server rejected robot package",
            )
            self.server.record_failure(failure)
            result.failures.append(failure)
            return result

        while True:
            try:
                message = self._next_step_with_retry(result)
            except TimeoutError as exc:
                failure = FailureMessage(FailureCategory.TIMEOUT, str(exc))
                self.server.record_failure(failure)
                result.failures.append(failure)
                return result
            except ProtocolError as exc:
                # Real transport surfaces server-side action rejection and
                # other protocol mismatches as ProtocolError. Map to the
                # closest technical-failure category.
                category = (
                    FailureCategory.INVALID_ACTION
                    if "action" in str(exc).lower() or "step_id" in str(exc).lower()
                    else FailureCategory.COMPATIBILITY
                )
                failure = FailureMessage(category, str(exc))
                self.server.record_failure(failure)
                result.failures.append(failure)
                return result
            except _DisconnectErrorClass as exc:
                failure = FailureMessage(FailureCategory.DISCONNECT, str(exc))
                self.server.record_failure(failure)
                result.failures.append(failure)
                return result

            if isinstance(message, TerminalMessage):
                result.terminal = message
                return result

            if not isinstance(message, StepMessage):
                raise ProtocolError(f"server returned unexpected message: {type(message).__name__}")

            action_or_failure = self._run_step(message)
            if isinstance(action_or_failure, FailureMessage):
                self.server.record_failure(action_or_failure)
                result.failures.append(action_or_failure)
                return result

            action = action_or_failure
            self.server.submit_action(action)
            result.actions_sent += 1
            if not action.valid:
                result.failures.append(
                    FailureMessage(
                        FailureCategory.INVALID_ACTION,
                        action.invalid_reason or "invalid action",
                        step_id=message.step_id,
                    )
                )
                return result
            result.steps_completed += 1

    def _next_step_with_retry(self, result: ClientRunResult) -> StepMessage | TerminalMessage:
        attempts = 0
        while True:
            try:
                return self.server.next_step()
            except TimeoutError:
                if attempts >= self.config.retry_timeouts:
                    raise
                attempts += 1
                result.telemetry.append(
                    FailureMessage(
                        FailureCategory.TIMEOUT,
                        "Recovered transient timeout",
                        retry_count=attempts,
                    )
                )

    def _run_step(self, step: StepMessage) -> ActionMessage | FailureMessage:
        started = perf_counter()
        try:
            observation = self.transformer(step)
        except Exception as exc:
            reason = redact_text(str(exc) or exc.__class__.__name__)
            return FailureMessage(FailureCategory.TRANSFORMER_EXCEPTION, reason, step.step_id)

        try:
            action = self.policy(observation)
        except Exception as exc:
            reason = redact_text(str(exc) or exc.__class__.__name__)
            return FailureMessage(FailureCategory.POLICY_EXCEPTION, reason, step.step_id)

        latency_ms = (perf_counter() - started) * 1000
        action_vector, invalid_reason = self._coerce_action(action)
        return ActionMessage(
            step_id=step.step_id,
            action=action_vector,
            latency_ms=latency_ms,
            metadata={"sim_time": step.sim_time, "control_dt": step.control_dt},
            invalid_reason=invalid_reason,
        )

    def _coerce_action(self, action: object) -> tuple[list[float], str | None]:
        if not isinstance(action, (list, tuple)):
            return [], "policy action must be a list or tuple"
        try:
            action_vector = [float(value) for value in action]
        except (TypeError, ValueError):
            return [], "policy action values must be numeric"
        if len(action_vector) != self.config.action_size:
            return action_vector, (
                f"policy action length {len(action_vector)} does not match "
                f"declared action size {self.config.action_size}"
            )
        return action_vector, None

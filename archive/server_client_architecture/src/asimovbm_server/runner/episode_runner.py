"""Server-owned episode lifecycle over simulation adapters."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from asimovbm_protocol import ActionMessage, FailureCategory, StepMessage, TerminalStatus
from asimovbm_server.simulation import (
    SimulationSetupError,
    SimulationSmokeResult,
    SimulationStepError,
)

from .telemetry import (
    TechnicalDiagnostic,
    TelemetryValidationError,
    copy_smoke_result,
    validate_step_telemetry,
)


class BatchSimulationAdapter(Protocol):
    def run(self) -> SimulationSmokeResult: ...


class StepSimulationAdapter(Protocol):
    @property
    def terminal(self) -> bool: ...
    def next_step(self) -> StepMessage: ...
    def apply_action(self, action: ActionMessage): ...
    def smoke_result(self) -> SimulationSmokeResult: ...


PolicyChannel = Callable[[StepMessage], ActionMessage]


@dataclass(frozen=True)
class EpisodeRunnerConfig:
    max_attempts: int = 2


@dataclass(frozen=True)
class EpisodeRunResult:
    status: TerminalStatus
    attempts: int
    valid_episodes: int
    smoke_results: tuple[SimulationSmokeResult, ...] = ()
    technical_diagnostics: tuple[TechnicalDiagnostic, ...] = ()
    reliability: dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == TerminalStatus.REPORT_READY and self.valid_episodes > 0


class EpisodeRunner:
    """Runs batch or policy-in-loop smoke episodes without transport concerns."""

    def __init__(self, config: EpisodeRunnerConfig | None = None) -> None:
        self.config = config or EpisodeRunnerConfig()

    def run_batch(
        self,
        adapter_factory: Callable[[], BatchSimulationAdapter],
    ) -> EpisodeRunResult:
        diagnostics: list[TechnicalDiagnostic] = []
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                smoke = copy_smoke_result(adapter_factory().run())
                return _result(
                    TerminalStatus.REPORT_READY,
                    attempts=attempt,
                    valid_episodes=1,
                    smoke_results=[smoke],
                    diagnostics=diagnostics,
                )
            except SimulationSetupError as exc:
                diagnostics.append(
                    TechnicalDiagnostic(FailureCategory.SETUP, str(exc), attempt)
                )
            except Exception as exc:
                diagnostics.append(
                    TechnicalDiagnostic(
                        FailureCategory.COMPATIBILITY,
                        f"batch adapter failed: {exc}",
                        attempt,
                    )
                )
        return _result(
            TerminalStatus.FAILED,
            attempts=self.config.max_attempts,
            valid_episodes=0,
            smoke_results=[],
            diagnostics=diagnostics,
        )

    def run_policy_in_loop(
        self,
        adapter_factory: Callable[[], StepSimulationAdapter],
        policy_channel: PolicyChannel,
    ) -> EpisodeRunResult:
        diagnostics: list[TechnicalDiagnostic] = []
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                adapter = adapter_factory()
                while not adapter.terminal:
                    step = adapter.next_step()
                    validate_step_telemetry(step)
                    action = policy_channel(step)
                    if not isinstance(action, ActionMessage):
                        raise SimulationStepError(
                            "policy channel must return ActionMessage"
                        )
                    adapter.apply_action(action)
                smoke = copy_smoke_result(adapter.smoke_result())
                return _result(
                    TerminalStatus.REPORT_READY,
                    attempts=attempt,
                    valid_episodes=1,
                    smoke_results=[smoke],
                    diagnostics=diagnostics,
                )
            except TelemetryValidationError as exc:
                diagnostics.append(
                    TechnicalDiagnostic(FailureCategory.SETUP, str(exc), attempt)
                )
            except SimulationStepError as exc:
                diagnostics.append(
                    TechnicalDiagnostic(
                        FailureCategory.INVALID_ACTION,
                        str(exc),
                        attempt,
                    )
                )
            except SimulationSetupError as exc:
                diagnostics.append(
                    TechnicalDiagnostic(FailureCategory.SETUP, str(exc), attempt)
                )
            except Exception as exc:
                diagnostics.append(
                    TechnicalDiagnostic(
                        FailureCategory.POLICY_EXCEPTION,
                        f"policy channel failed: {exc}",
                        attempt,
                    )
                )
        return _result(
            TerminalStatus.FAILED,
            attempts=self.config.max_attempts,
            valid_episodes=0,
            smoke_results=[],
            diagnostics=diagnostics,
        )


def _result(
    status: TerminalStatus,
    *,
    attempts: int,
    valid_episodes: int,
    smoke_results: list[SimulationSmokeResult],
    diagnostics: list[TechnicalDiagnostic],
) -> EpisodeRunResult:
    return EpisodeRunResult(
        status=status,
        attempts=attempts,
        valid_episodes=valid_episodes,
        smoke_results=tuple(smoke_results),
        technical_diagnostics=tuple(diagnostics),
        reliability={
            "attempts": attempts,
            "technical_failures": len(diagnostics),
            "valid_episodes": valid_episodes,
        },
    )

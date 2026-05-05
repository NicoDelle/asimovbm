from __future__ import annotations

from itertools import count

from asimovbm_protocol import ActionMessage, FailureCategory, TerminalStatus
from asimovbm_server.runner import EpisodeRunner, EpisodeRunnerConfig
from asimovbm_server.simulation import (
    FakeSmokeSimulation,
    G1SlamBatchAdapter,
    G1SlamBatchConfig,
    G1SlamStepper,
    G1SlamStepperConfig,
    fake_step,
)


def _zero_policy(step):
    return ActionMessage(step.step_id, [0.0, 0.0], latency_ms=1.0)


def test_episode_runner_completes_fake_policy_in_loop_episode() -> None:
    runner = EpisodeRunner(EpisodeRunnerConfig(max_attempts=1))

    result = runner.run_policy_in_loop(
        lambda: FakeSmokeSimulation([fake_step(1), fake_step(2, sim_time=0.025)]),
        _zero_policy,
    )

    assert result.ok
    assert result.status == TerminalStatus.REPORT_READY
    assert result.valid_episodes == 1
    assert result.reliability == {
        "attempts": 1,
        "technical_failures": 0,
        "valid_episodes": 1,
    }
    assert result.smoke_results[0].maturity == "fake_protocol"
    assert result.smoke_results[0].steps == 2


def test_episode_runner_runs_g1_batch_without_websocket() -> None:
    runner = EpisodeRunner(EpisodeRunnerConfig(max_attempts=1))

    result = runner.run_batch(
        lambda: G1SlamBatchAdapter(G1SlamBatchConfig(steps=6))
    )

    assert result.ok
    assert result.smoke_results[0].maturity == "g1_slam_batch_smoke"
    assert result.smoke_results[0].trajectory_summary["points"] == 7


def test_episode_runner_runs_g1_policy_in_loop_without_websocket() -> None:
    runner = EpisodeRunner(EpisodeRunnerConfig(max_attempts=1))

    def policy(step):
        plan = next(sensor for sensor in step.sensors if sensor.name == "navigation_plan")
        command = plan.data["recommended_command"]
        return ActionMessage(step.step_id, [command["linear"], command["yaw_rate"]], 1.0)

    result = runner.run_policy_in_loop(
        lambda: G1SlamStepper.from_config(
            G1SlamStepperConfig(max_steps=1, lidar_rays=9)
        ),
        policy,
    )

    assert result.ok
    assert result.smoke_results[0].maturity == "g1_slam_policy_in_loop_smoke"
    assert result.smoke_results[0].steps == 1


def test_technical_failure_consumes_attempt_then_retries() -> None:
    attempts = count(1)

    def flaky_policy(step):
        if next(attempts) == 1:
            raise RuntimeError("policy channel unavailable")
        return ActionMessage(step.step_id, [0.0, 0.0], latency_ms=1.0)

    result = EpisodeRunner(EpisodeRunnerConfig(max_attempts=2)).run_policy_in_loop(
        lambda: FakeSmokeSimulation([fake_step()]),
        flaky_policy,
    )

    assert result.ok
    assert result.attempts == 2
    assert result.valid_episodes == 1
    assert len(result.technical_diagnostics) == 1
    assert result.technical_diagnostics[0].category == FailureCategory.POLICY_EXCEPTION
    assert result.reliability["technical_failures"] == 1


def test_missing_pose_telemetry_fails_without_behavioral_episode() -> None:
    bad_step = fake_step()
    bad_step = type(bad_step)(
        step_id=bad_step.step_id,
        sim_time=bad_step.sim_time,
        control_dt=bad_step.control_dt,
        sensors=[],
        task_events=bad_step.task_events,
    )

    result = EpisodeRunner(EpisodeRunnerConfig(max_attempts=1)).run_policy_in_loop(
        lambda: FakeSmokeSimulation([bad_step]),
        _zero_policy,
    )

    assert not result.ok
    assert result.status == TerminalStatus.FAILED
    assert result.valid_episodes == 0
    assert result.technical_diagnostics[0].category == FailureCategory.SETUP

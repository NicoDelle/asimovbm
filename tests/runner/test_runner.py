import unittest

from asimovbm_client.protocol import (
    FailureCategory,
    PackageSubmission,
    SensorReading,
    StepMessage,
    TaskEvent,
    TerminalStatus,
)
from asimovbm_client.runner import RunnerConfig, StepSynchronousRunner
from asimovbm_client.testing import FakeBenchmarkServer, FakeServerScript


def package(action_size=2):
    return PackageSubmission(
        "testbot",
        {"format": "mjcf"},
        [{"name": "proprioception", "kind": "robot_state"}],
        {"mode": "joint_target", "joints": [f"j{i}" for i in range(action_size)]},
    )


def step(step_id=1):
    return StepMessage(
        step_id,
        0.0,
        0.025,
        [SensorReading("proprioception", "robot_state", {"joint_positions": [0.0]})],
        [TaskEvent("come_here", {"target_id": "human_1"})],
    )


class RunnerTests(unittest.TestCase):
    def test_runner_completes_against_fake_server(self):
        server = FakeBenchmarkServer(FakeServerScript([step()]))
        seen = {}

        def transformer(message):
            seen["events"] = [event.name for event in message.task_events]
            return {"ok": True}

        def policy(observation):
            return [0.0, 0.0]

        result = StepSynchronousRunner(
            server,
            package(),
            transformer,
            policy,
            RunnerConfig("run-1", action_size=2),
        ).run()

        self.assertIsNotNone(result.terminal)
        self.assertEqual(result.steps_completed, 1)
        self.assertEqual(seen["events"], ["come_here"])
        self.assertEqual(server.actions[0].metadata["control_dt"], 0.025)

    def test_validation_failure_stops_before_policy_execution(self):
        server = FakeBenchmarkServer(FakeServerScript([step()], validation_errors=["bad"]))
        called = {"policy": False}

        def policy(_observation):
            called["policy"] = True
            return [0.0, 0.0]

        result = StepSynchronousRunner(
            server,
            package(),
            lambda message: message,
            policy,
            RunnerConfig("run-1", action_size=2),
        ).run()

        self.assertIsNone(result.terminal)
        self.assertFalse(called["policy"])

    def test_transformer_exception_emits_failure(self):
        server = FakeBenchmarkServer(FakeServerScript([step()]))

        def transformer(_message):
            raise RuntimeError("boom token=secret")

        result = StepSynchronousRunner(
            server,
            package(),
            transformer,
            lambda _observation: [0.0, 0.0],
            RunnerConfig("run-1", action_size=2),
        ).run()

        self.assertTrue(result.failures)
        self.assertEqual(result.failures[0].category, FailureCategory.TRANSFORMER_EXCEPTION)
        self.assertIn("<redacted>", result.failures[0].summary)
        self.assertFalse(server.actions)
        self.assertEqual(server.failures[0].category, FailureCategory.TRANSFORMER_EXCEPTION)

    def test_policy_exception_emits_failure_without_submitting_action(self):
        server = FakeBenchmarkServer(FakeServerScript([step()]))

        def policy(_observation):
            raise RuntimeError("policy failed")

        result = StepSynchronousRunner(
            server,
            package(),
            lambda message: message,
            policy,
            RunnerConfig("run-1", action_size=2),
        ).run()

        self.assertEqual(result.failures[0].category, FailureCategory.POLICY_EXCEPTION)
        self.assertFalse(server.actions)
        self.assertEqual(server.failures[0].category, FailureCategory.POLICY_EXCEPTION)

    def test_invalid_action_shape_stops_as_invalid_action(self):
        server = FakeBenchmarkServer(FakeServerScript([step()]))
        result = StepSynchronousRunner(
            server,
            package(),
            lambda message: message,
            lambda _observation: [0.0],
            RunnerConfig("run-1", action_size=2),
        ).run()

        self.assertEqual(result.failures[-1].category.value, "invalid_action")
        self.assertTrue(server.actions[0].invalid_reason)

    def test_one_transient_timeout_is_retried_and_recorded(self):
        server = FakeBenchmarkServer(FakeServerScript([step()], fail_once_on_step=1))
        result = StepSynchronousRunner(
            server,
            package(),
            lambda message: message,
            lambda _observation: [0.0, 0.0],
            RunnerConfig("run-1", action_size=2),
        ).run()

        self.assertIsNotNone(result.terminal)
        self.assertTrue(any(item.category.value == "timeout" for item in result.telemetry))
        self.assertFalse(result.failures)
        self.assertEqual(result.steps_completed, 1)

    def test_failed_terminal_status_is_not_ok(self):
        server = FakeBenchmarkServer(
            FakeServerScript([step()], terminal_status=TerminalStatus.FAILED)
        )
        result = StepSynchronousRunner(
            server,
            package(),
            lambda message: message,
            lambda _observation: [0.0, 0.0],
            RunnerConfig("run-1", action_size=2),
        ).run()

        self.assertIsNotNone(result.terminal)
        self.assertFalse(result.ok)

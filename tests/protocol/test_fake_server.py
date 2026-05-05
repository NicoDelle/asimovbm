import unittest

from asimovbm_client.protocol import (
    ActionMessage,
    FakeBenchmarkServer,
    FakeServerScript,
    FailureCategory,
    PackageSubmission,
    PROTOCOL_VERSION,
    ProtocolError,
    SensorReading,
    SessionBootstrap,
    StepMessage,
    TerminalMessage,
    ValidationStatus,
)


def package():
    return PackageSubmission(
        "testbot",
        {"format": "mjcf", "path": "robot.xml"},
        [{"name": "lidar", "kind": "lidar"}],
        {"mode": "joint_target", "joints": ["x"]},
    )


def step():
    return StepMessage(1, 0.0, 0.025, [SensorReading("lidar", "lidar", [1.0])])


class FakeServerTests(unittest.TestCase):
    def test_happy_path_lifecycle(self):
        server = FakeBenchmarkServer(FakeServerScript([step()]))
        server.connect(SessionBootstrap("run-1"))
        response = server.submit_package(package())

        self.assertEqual(response.status, ValidationStatus.ACCEPTED)
        self.assertEqual(server.next_step(), step())
        server.submit_action(ActionMessage(1, [0.0], 1.2))
        self.assertIsInstance(server.next_step(), TerminalMessage)
        self.assertEqual(server.actions[0].step_id, 1)

    def test_validation_failure_never_enters_control_loop(self):
        server = FakeBenchmarkServer(FakeServerScript([step()], validation_errors=["bad package"]))
        server.connect(SessionBootstrap("run-1"))

        response = server.submit_package(package())

        self.assertEqual(response.status, ValidationStatus.REJECTED)
        self.assertEqual(response.errors, ["bad package"])

    def test_rejects_unsupported_protocol_version(self):
        server = FakeBenchmarkServer(FakeServerScript([step()], supported_protocol_version=PROTOCOL_VERSION))

        with self.assertRaises(ProtocolError):
            server.connect(SessionBootstrap("run-1", protocol_version="wrong"))

    def test_records_invalid_action_as_technical_failure(self):
        server = FakeBenchmarkServer(FakeServerScript([step()]))
        server.connect(SessionBootstrap("run-1"))
        server.submit_package(package())

        server.submit_action(ActionMessage(1, [], 0.1, invalid_reason="wrong shape"))

        self.assertEqual(server.failures[0].category, FailureCategory.INVALID_ACTION)

    def test_sensor_freshness_metadata_is_preserved(self):
        stale = SensorReading("camera", "rgb", {"uri": "frame-1"}, fresh=False, metadata={"carried_from": 1})
        message = StepMessage(2, 0.025, 0.025, [stale])

        self.assertFalse(message.sensors[0].fresh)
        self.assertEqual(message.sensors[0].metadata, {"carried_from": 1})

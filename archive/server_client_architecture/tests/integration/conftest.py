"""Integration test scaffolding.

Boots a real uvicorn server on an ephemeral port in a background thread so
``websockets.sync.client`` can dial a real TCP socket. ``TestClient`` is
not enough here because the synchronous WebSocket client requires a
network socket, not the in-process ASGI transport.
"""

from __future__ import annotations

import socket
import threading
import time
from contextlib import closing
from pathlib import Path

import pytest
import uvicorn
from fastapi import FastAPI

from asimovbm_protocol import (
    PackageSubmission,
    SensorReading,
    StepMessage,
    TaskEvent,
    TerminalStatus,
)
from asimovbm_server import ServerConfig, SessionManager, create_app
from asimovbm_server.runner import ScriptedLifecycleOrchestrator

BOOTSTRAP_TOKEN = "integration-bootstrap-token"


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_port(port: int, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
            s.settimeout(0.1)
            try:
                s.connect(("127.0.0.1", port))
                return
            except OSError:
                time.sleep(0.05)
    raise TimeoutError(f"server on 127.0.0.1:{port} did not become ready")


def _sample_steps() -> list[StepMessage]:
    return [
        StepMessage(
            step_id=1,
            sim_time=0.0,
            control_dt=0.025,
            sensors=[
                SensorReading("pose", "proprioception", {"x": 0.0, "y": 0.0}),
                SensorReading("lidar", "lidar", [1.5, 1.5, 1.5]),
            ],
            task_events=[TaskEvent("come_here", {"target_id": "h1"})],
        ),
        StepMessage(
            step_id=2,
            sim_time=0.025,
            control_dt=0.025,
            sensors=[
                SensorReading("pose", "proprioception", {"x": 0.1, "y": 0.0}),
                SensorReading("lidar", "lidar", [1.4, 1.4, 1.4]),
            ],
        ),
    ]


@pytest.fixture()
def sample_steps() -> list[StepMessage]:
    return _sample_steps()


@pytest.fixture()
def sample_package() -> PackageSubmission:
    return PackageSubmission(
        name="testbot",
        model={"format": "mjcf", "path": "robot.xml"},
        sensors=[
            {"name": "pose", "kind": "proprioception"},
            {"name": "lidar", "kind": "lidar"},
        ],
        action_mapping={"mode": "joint_target", "joints": ["w1", "w2"]},
        robot_metadata={"forward_axis": "x+"},
    )


@pytest.fixture()
def server_factory(tmp_path: Path):
    """Return a factory that builds and runs a server with a configured
    orchestrator. Cleans up the background uvicorn thread on teardown."""

    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()

    threads: list[tuple[uvicorn.Server, threading.Thread]] = []

    def factory(
        steps: list[StepMessage] | None = None,
        *,
        orchestrator=None,
        terminal_status: TerminalStatus = TerminalStatus.REPORT_READY,
        delay_before_step_id: dict[int, float] | None = None,
        max_invalid_messages: int = 8,
        max_message_bytes: int = 1_048_576,
    ) -> tuple[FastAPI, SessionManager, str, ScriptedLifecycleOrchestrator]:
        config = ServerConfig(
            bootstrap_token=BOOTSTRAP_TOKEN,
            artifact_root=artifact_root,
            max_message_bytes=max_message_bytes,
            max_invalid_messages=max_invalid_messages,
            session_idle_timeout_s=30.0,
            allow_loopback_session_creation=False,
        )
        manager = SessionManager(config)
        if orchestrator is None:
            orchestrator = ScriptedLifecycleOrchestrator(
                manager,
                steps if steps is not None else _sample_steps(),
                terminal_status=terminal_status,
                delay_before_step_id=delay_before_step_id,
            )
        app = create_app(config, session_manager=manager, orchestrator=orchestrator)

        port = _free_port()
        server = uvicorn.Server(
            uvicorn.Config(
                app,
                host="127.0.0.1",
                port=port,
                log_level="warning",
                lifespan="on",
            )
        )
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        threads.append((server, thread))
        _wait_for_port(port)
        return app, manager, f"http://127.0.0.1:{port}", orchestrator

    yield factory

    for server, thread in threads:
        server.should_exit = True
        thread.join(timeout=5.0)


@pytest.fixture()
def echo_policy():
    """Simple participant code: returns a zero-vector action of declared length."""

    def transformer(step):
        return step

    def policy(observation):
        joints = 2
        return [0.0] * joints

    return transformer, policy

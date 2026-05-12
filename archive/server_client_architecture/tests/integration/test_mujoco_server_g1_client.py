from __future__ import annotations

from pathlib import Path

import pytest

from asimovbm_client.robot_package import load_robot_package
from asimovbm_client.runner import RunnerConfig, StepSynchronousRunner
from asimovbm_client.transport import TransportConfig, WebSocketBenchmarkServer
from asimovbm_server.runner import MuJoCoLifecycleOrchestrator
from examples.policies.g1_slam_policy import G1SlamPolicy, G1SlamTransformer

from .conftest import BOOTSTRAP_TOKEN

PACKAGE_ROOT = Path("examples/robot_packages/minimal")


def test_g1_style_client_policy_drives_server_owned_mujoco(server_factory) -> None:
    pytest.importorskip("mujoco")
    orchestrator = MuJoCoLifecycleOrchestrator(
        package_root=PACKAGE_ROOT,
        max_steps=3,
    )
    _, _, base_url, _ = server_factory(orchestrator=orchestrator)
    transport = WebSocketBenchmarkServer(
        TransportConfig(
            server_url=base_url,
            bootstrap_token=BOOTSTRAP_TOKEN,
            receive_timeout_s=3.0,
        )
    )

    try:
        result = StepSynchronousRunner(
            transport,
            load_robot_package(PACKAGE_ROOT),
            G1SlamTransformer(),
            G1SlamPolicy(),
            RunnerConfig("<server-issued>", action_size=2, participant_id="g1-example"),
        ).run()
    finally:
        transport.close()

    assert result.ok
    assert result.steps_completed == 3
    assert orchestrator.last_adapter is not None
    report = orchestrator.last_adapter.smoke_result()
    assert report.maturity == "mujoco_mobile_base_smoke"
    assert report.steps == 3
    assert report.final_pose["x"] > 0.0


def test_g1_policy_example_does_not_import_server_simulation() -> None:
    source = Path("examples/policies/g1_slam_policy.py").read_text(encoding="utf-8")

    assert "asimovbm_server" not in source

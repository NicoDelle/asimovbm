from __future__ import annotations

from pathlib import Path

import pytest

from asimovbm_server.simulation import (
    G1SlamBatchAdapter,
    G1SlamBatchConfig,
    SimulationSetupError,
)


def test_batch_adapter_runs_pure_python_navigation_smoke() -> None:
    result = G1SlamBatchAdapter(G1SlamBatchConfig(steps=16)).run()

    assert result.maturity == "g1_slam_batch_smoke"
    assert result.steps == 16
    assert result.trajectory_summary["points"] == 17
    assert "x" in result.final_pose
    assert result.telemetry["grid"]["observed_cells"] > 0
    assert result.telemetry["last_path"]["points"] >= 0


def test_batch_adapter_raises_clear_setup_error_for_missing_config(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing-navigation.json"

    with pytest.raises(SimulationSetupError, match="does not exist"):
        G1SlamBatchAdapter(G1SlamBatchConfig(config_path=missing)).run()

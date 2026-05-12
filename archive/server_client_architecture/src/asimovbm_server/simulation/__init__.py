"""Simulation adapters for server-owned benchmark smoke paths."""

from .base import SimulationSetupError, SimulationSmokeResult, SimulationStepError
from .fake import FakeSmokeSimulation, fake_step
from .mujoco_adapter import MuJoCoAdapterConfig, MuJoCoSimulationAdapter, mujoco_available

_G1_EXPORTS = {
    "G1SlamBatchAdapter",
    "G1SlamBatchConfig",
    "G1SlamStepOutcome",
    "G1SlamStepper",
    "G1SlamStepperConfig",
}

__all__ = [
    "FakeSmokeSimulation",
    "MuJoCoAdapterConfig",
    "MuJoCoSimulationAdapter",
    "SimulationSetupError",
    "SimulationSmokeResult",
    "SimulationStepError",
    "fake_step",
    "mujoco_available",
]


def __getattr__(name: str):
    if name not in _G1_EXPORTS:
        raise AttributeError(name)
    if name in {"G1SlamBatchAdapter", "G1SlamBatchConfig"}:
        from .g1_slam_adapter import G1SlamBatchAdapter, G1SlamBatchConfig

        return {
            "G1SlamBatchAdapter": G1SlamBatchAdapter,
            "G1SlamBatchConfig": G1SlamBatchConfig,
        }[name]
    from .g1_slam_stepper import G1SlamStepOutcome, G1SlamStepper, G1SlamStepperConfig

    return {
        "G1SlamStepOutcome": G1SlamStepOutcome,
        "G1SlamStepper": G1SlamStepper,
        "G1SlamStepperConfig": G1SlamStepperConfig,
    }[name]

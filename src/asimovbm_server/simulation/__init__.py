"""Simulation adapters for server-owned benchmark smoke paths."""

from .base import SimulationSetupError, SimulationSmokeResult, SimulationStepError
from .fake import FakeSmokeSimulation, fake_step
from .g1_slam_adapter import G1SlamBatchAdapter, G1SlamBatchConfig
from .g1_slam_stepper import G1SlamStepOutcome, G1SlamStepper, G1SlamStepperConfig

__all__ = [
    "FakeSmokeSimulation",
    "G1SlamBatchAdapter",
    "G1SlamBatchConfig",
    "G1SlamStepOutcome",
    "G1SlamStepper",
    "G1SlamStepperConfig",
    "SimulationSetupError",
    "SimulationSmokeResult",
    "SimulationStepError",
    "fake_step",
]

"""Robot embodiment adapters for validation runs."""

from .base import FakeMobileBaseRobot, RobotAdapter, RobotProfile, RobotState
from .registry import RobotRegistry, default_robot_registry

__all__ = [
    "FakeMobileBaseRobot",
    "RobotAdapter",
    "RobotProfile",
    "RobotRegistry",
    "RobotState",
    "default_robot_registry",
]

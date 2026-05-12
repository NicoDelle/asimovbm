"""Robot embodiment adapters for validation runs."""

from .base import FakeMobileBaseRobot, RobotAdapter, RobotProfile, RobotState
from .mujoco_kinematic import KinematicMuJoCoRobot, RobotProfileSetupError
from .registry import RobotRegistry, default_robot_registry, load_robot_profiles
from .robojudo_adapter import RoboJudoRobot

__all__ = [
    "FakeMobileBaseRobot",
    "KinematicMuJoCoRobot",
    "RobotAdapter",
    "RobotProfile",
    "RobotProfileSetupError",
    "RobotRegistry",
    "RobotState",
    "RoboJudoRobot",
    "default_robot_registry",
    "load_robot_profiles",
]

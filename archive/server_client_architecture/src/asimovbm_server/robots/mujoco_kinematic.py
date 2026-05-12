"""Kinematic robot adapters with explicit MuJoCo asset setup diagnostics."""

from __future__ import annotations

from .base import FakeMobileBaseRobot, RobotProfile


class RobotProfileSetupError(RuntimeError):
    """Raised when a selected robot profile cannot be initialized."""


class KinematicMuJoCoRobot(FakeMobileBaseRobot):
    """Mobile-base validation adapter for robot profiles that may name MJCF assets.

    The local-validation MVP still uses the shared [linear_velocity, yaw_rate]
    contract. Asset-backed profiles are allowed only when their declared model
    path exists, so visible runs cannot silently show a marker in place of a
    missing G1/Go2 model.
    """

    def __init__(self, profile: RobotProfile) -> None:
        if profile.asset_backed and (profile.model_path is None or not profile.model_path.exists()):
            raise RobotProfileSetupError(
                f"robot profile {profile.id!r} requires MuJoCo asset path "
                f"{profile.model_path}; install the asset or use a marker-only profile"
            )
        super().__init__(profile)

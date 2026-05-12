"""Optional MuJoCo viewer hooks for validation runs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ViewerHandle:
    viewer: Any | None = None

    def sync(self) -> None:
        if self.viewer is not None:
            self.viewer.sync()

    def close(self) -> None:
        if self.viewer is not None:
            self.viewer.close()


def maybe_open_viewer(robot, *, enabled: bool) -> ViewerHandle:
    if not enabled:
        return ViewerHandle()
    target = robot.viewer_target()
    if target is None:
        return ViewerHandle()
    model, data = target
    import mujoco.viewer

    return ViewerHandle(mujoco.viewer.launch_passive(model, data))

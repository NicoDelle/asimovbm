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


def maybe_open_viewer(*targets, enabled: bool) -> ViewerHandle:
    if not enabled:
        return ViewerHandle()
    target = _first_viewer_target(targets)
    if target is None:
        return ViewerHandle()
    model, data = target
    import mujoco
    import mujoco.viewer

    viewer = mujoco.viewer.launch_passive(model, data)
    _configure_default_camera(viewer, model, mujoco)
    return ViewerHandle(viewer)


def _first_viewer_target(targets) -> tuple[Any, Any] | None:
    for target in targets:
        if target is None:
            continue
        if isinstance(target, tuple) and len(target) == 2:
            return target
        viewer_target = getattr(target, "viewer_target", None)
        if callable(viewer_target):
            resolved = viewer_target()
            if resolved is not None:
                return resolved
    return None


def _configure_default_camera(viewer: Any, model: Any, mujoco: Any) -> None:
    cam = getattr(viewer, "cam", None)
    if cam is None:
        return
    try:
        cam.type = mujoco.mjtCamera.mjCAMERA_FREE
    except AttributeError:
        pass
    center = getattr(getattr(model, "stat", None), "center", None)
    if center is not None:
        cam.lookat[0] = float(center[0])
        cam.lookat[1] = float(center[1])
        cam.lookat[2] = float(center[2])
    extent = float(getattr(getattr(model, "stat", None), "extent", 6.0) or 6.0)
    cam.distance = max(8.0, 1.7 * extent)
    cam.azimuth = 90.0
    cam.elevation = -65.0

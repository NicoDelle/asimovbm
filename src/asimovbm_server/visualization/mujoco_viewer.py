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
    import mujoco.viewer

    return ViewerHandle(mujoco.viewer.launch_passive(model, data))


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

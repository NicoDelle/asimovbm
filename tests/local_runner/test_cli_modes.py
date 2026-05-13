from __future__ import annotations

import pytest

from asimovbm.local_runner.cli import build_parser
from asimovbm.local_runner.runner import LocalRunConfig


def test_iteration_count_controls_default_viewer_mode() -> None:
    assert LocalRunConfig(iterations=1).resolved_visible() is True
    assert LocalRunConfig(iterations=2).resolved_visible() is False
    assert LocalRunConfig(iterations=2, visible=True).resolved_visible() is True
    assert LocalRunConfig(iterations=1, visible=False).resolved_visible() is False


def test_viewer_speed_defaults_fast_but_can_be_realtime() -> None:
    assert LocalRunConfig().viewer_speed == 4.0
    assert build_parser().parse_args(["--robot", "g1"]).viewer_speed == 4.0
    assert build_parser().parse_args(["--robot", "g1", "--viewer-speed", "1"]).viewer_speed == 1.0


def test_visible_and_headless_flags_are_mutually_exclusive() -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["--robot", "g1", "--visible", "--headless"])


def test_robot_is_required_to_avoid_mixed_robot_benchmark_runs() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--iterations", "1"])

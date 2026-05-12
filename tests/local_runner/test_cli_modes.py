from __future__ import annotations

import pytest

from asimovbm.local_runner.cli import build_parser
from asimovbm.local_runner.runner import LocalRunConfig


def test_iteration_count_controls_default_viewer_mode() -> None:
    assert LocalRunConfig(iterations=1).resolved_visible() is True
    assert LocalRunConfig(iterations=2).resolved_visible() is False
    assert LocalRunConfig(iterations=2, visible=True).resolved_visible() is True
    assert LocalRunConfig(iterations=1, visible=False).resolved_visible() is False


def test_visible_and_headless_flags_are_mutually_exclusive() -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["--visible", "--headless"])


def test_measurement_backend_selector_defaults_to_reference() -> None:
    parser = build_parser()

    args = parser.parse_args([])

    assert args.measurement_backend == "reference"


def test_measurement_backend_selector_accepts_mujoco_and_rejects_unknown() -> None:
    parser = build_parser()

    assert parser.parse_args(["--measurement-backend", "mujoco"]).measurement_backend == "mujoco"
    with pytest.raises(SystemExit):
        parser.parse_args(["--measurement-backend", "simulator"])

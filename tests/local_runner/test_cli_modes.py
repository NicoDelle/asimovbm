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


def test_camera_view_defaults_to_config_but_can_match_survey_pov() -> None:
    assert LocalRunConfig().camera_view == "config"
    assert build_parser().parse_args(["--robot", "g1"]).camera_view == "config"
    assert build_parser().parse_args(["--robot", "g1", "--camera-view", "arrival"]).camera_view == "arrival"


def test_start_delay_can_be_overridden_for_hand_matching() -> None:
    assert LocalRunConfig().start_delay_s is None
    assert build_parser().parse_args(["--robot", "g1", "--start-delay", "0"]).start_delay_s == 0.0
    with pytest.raises(ValueError, match="start_delay must be >= 0"):
        LocalRunConfig(robot_id="g1", start_delay_s=-0.1).validate()


def test_route_y_offset_can_be_overridden_for_hand_matching() -> None:
    assert LocalRunConfig().route_y_offset_m is None
    assert build_parser().parse_args(["--robot", "g1", "--route-y-offset", "0.6"]).route_y_offset_m == 0.6


def test_start_x_offset_can_be_overridden_for_hand_matching() -> None:
    assert LocalRunConfig().start_x_offset_m is None
    assert build_parser().parse_args(["--robot", "g1", "--start-x-offset", "0.2"]).start_x_offset_m == 0.2


def test_g1_unitree_robojudo_policy_is_selectable() -> None:
    args = build_parser().parse_args(["--robot", "g1", "--policy", "g1_robojudo_unitree"])

    assert args.policy == "g1_robojudo_unitree"


def test_g1_survey_policy_labels_must_match_selected_profile() -> None:
    with pytest.raises(ValueError, match="maps to survey policy_b"):
        LocalRunConfig(
            robot_id="g1",
            policy_id="g1_robojudo_asap",
            survey_export=True,
            survey_policy_id="policy_a",
        ).validate()


def test_visible_and_headless_flags_are_mutually_exclusive() -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["--robot", "g1", "--visible", "--headless"])


def test_survey_video_defaults_are_browser_quality() -> None:
    args = build_parser().parse_args(["--robot", "g1"])

    assert args.survey_video_fps == 24
    assert args.survey_video_width == 1280
    assert args.survey_video_height == 720


def test_robot_is_required_to_avoid_mixed_robot_benchmark_runs() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--iterations", "1"])

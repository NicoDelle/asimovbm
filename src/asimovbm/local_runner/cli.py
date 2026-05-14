"""Command-line entry point for local Paper HRI validation."""

from __future__ import annotations

import argparse
from pathlib import Path

from .catalog import (
    DEFAULT_EPISODE_IDS,
    DEFAULT_POLICY_BY_ROBOT,
    POLICY_IDS,
    ROBOT_IDS,
    EpisodeCatalogError,
)
from .runner import LocalRunConfig, run_local_validation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="asimovbm-local")
    parser.add_argument("--artifact-root", type=Path, default=Path("artifacts/local-validation"))
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument(
        "--robot",
        choices=ROBOT_IDS,
        required=True,
        help="Robot under test. A run never mixes robots.",
    )
    parser.add_argument(
        "--policy",
        choices=POLICY_IDS,
        help=(
            "Policy profile to test. Defaults by robot: "
            + ", ".join(f"{robot}={policy}" for robot, policy in DEFAULT_POLICY_BY_ROBOT.items())
            + "."
        ),
    )
    parser.add_argument(
        "--policy-path",
        type=Path,
        help="Override the selected policy profile's policy_path, for local policy files.",
    )
    parser.add_argument(
        "--viewer-speed",
        type=float,
        default=4.0,
        help="Visible playback speed multiplier; use 1.0 for realtime.",
    )
    parser.add_argument(
        "--camera-view",
        choices=("config", "arrival", "bystander"),
        default="config",
        help=(
            "Visible viewer POV. config uses the episode JSON default; "
            "arrival and bystander use the named camera_views from the episode JSON."
        ),
    )
    parser.add_argument(
        "--episode-steps",
        type=int,
        help=(
            "Override each selected episode's configured step count. "
            "The local trace backend uses 0.08 seconds per step; lower values shorten manual viewer runs."
        ),
    )
    parser.add_argument(
        "--start-delay",
        type=float,
        dest="start_delay_s",
        help=(
            "Override controller.start_delay_s in seconds. "
            "Use 0 for immediate navigation commands in hand-matched survey runs."
        ),
    )
    parser.add_argument(
        "--route-y-offset",
        type=float,
        dest="route_y_offset_m",
        help=(
            "Shift the selected route laterally on the world y-axis in meters. "
            "Useful for hand-matching the dynamic NPC pass side."
        ),
    )
    parser.add_argument(
        "--start-x-offset",
        type=float,
        dest="start_x_offset_m",
        help=(
            "Shift only the selected episode start pose on the world x-axis in meters. "
            "Positive values move the robot forward toward the point-to-point goal."
        ),
    )
    parser.add_argument(
        "--episode",
        action="append",
        choices=DEFAULT_EPISODE_IDS,
        dest="episodes",
        help="Run only the selected canonical episode id. May be passed more than once.",
    )
    parser.add_argument(
        "--survey-export",
        action="store_true",
        help="Render survey MP4 videos and JSON sidecars for each episode/view.",
    )
    parser.add_argument(
        "--survey-root",
        type=Path,
        default=Path("artifacts/survey"),
        help="Root for survey videos, JSON sidecars, and metric summaries.",
    )
    parser.add_argument(
        "--survey-policy-id",
        help="Policy folder name for survey export, e.g. policy_a or policy_b.",
    )
    parser.add_argument(
        "--survey-view",
        action="append",
        choices=("arrival", "bystander"),
        dest="survey_views",
        help="Survey camera view to export. Defaults to arrival and bystander.",
    )
    parser.add_argument(
        "--survey-video-fps",
        type=int,
        default=24,
        help="Frame rate for generated survey videos.",
    )
    parser.add_argument(
        "--survey-video-width",
        type=int,
        default=1280,
        help="Pixel width for generated survey videos.",
    )
    parser.add_argument(
        "--survey-video-height",
        type=int,
        default=720,
        help="Pixel height for generated survey videos.",
    )
    parser.add_argument(
        "--survey-video-max-duration",
        type=float,
        default=15.0,
        help="Maximum survey video duration in seconds; use 0 to preserve full episode duration.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--visible", action="store_true", help="force visible validation mode")
    mode.add_argument("--headless", action="store_true", help="force headless metric collection mode")
    parser.add_argument("--run-id", help="stable run id for artifact paths")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    visible = True if args.visible else False if args.headless else None
    try:
        result = run_local_validation(
            LocalRunConfig(
                artifact_root=args.artifact_root,
                iterations=args.iterations,
                robot_id=args.robot,
                policy_id=args.policy,
                policy_path=args.policy_path,
                episode_ids=tuple(args.episodes or ()),
                visible=visible,
                viewer_speed=args.viewer_speed,
                camera_view=args.camera_view,
                episode_steps=args.episode_steps,
                start_delay_s=args.start_delay_s,
                start_x_offset_m=args.start_x_offset_m,
                route_y_offset_m=args.route_y_offset_m,
                survey_export=args.survey_export,
                survey_root=args.survey_root,
                survey_policy_id=args.survey_policy_id,
                survey_views=tuple(args.survey_views or ("arrival", "bystander")),
                survey_video_fps=args.survey_video_fps,
                survey_video_width=args.survey_video_width,
                survey_video_height=args.survey_video_height,
                survey_video_max_duration_s=args.survey_video_max_duration or None,
                run_id=args.run_id,
            )
        )
    except (EpisodeCatalogError, ValueError) as exc:
        build_parser().error(str(exc))
    print(f"local validation run: {result.run_id}")
    print(f"manifest: {result.manifest_path}")
    print(f"report: {result.report_path}")
    print(f"metrics csv: {result.metrics_csv_path}")
    if result.survey_export is not None:
        print(f"survey videos: {result.survey_export.video_root}")
        print(f"survey json: {result.survey_export.json_root}")
        print(f"survey metrics: {result.survey_export.summary_json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

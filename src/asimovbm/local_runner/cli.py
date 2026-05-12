"""Command-line entry point for local Paper HRI validation."""

from __future__ import annotations

import argparse
from pathlib import Path

from .catalog import DEFAULT_EPISODE_IDS
from .runner import LocalRunConfig, run_local_validation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="asimovbm-local")
    parser.add_argument("--artifact-root", type=Path, default=Path("artifacts/local-validation"))
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument(
        "--viewer-speed",
        type=float,
        default=4.0,
        help="Visible playback speed multiplier; use 1.0 for realtime.",
    )
    parser.add_argument(
        "--episode",
        action="append",
        choices=DEFAULT_EPISODE_IDS,
        dest="episodes",
        help="Run only the selected canonical episode id. May be passed more than once.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--visible", action="store_true", help="force visible validation mode")
    mode.add_argument("--headless", action="store_true", help="force headless metric collection mode")
    parser.add_argument("--run-id", help="stable run id for artifact paths")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    visible = True if args.visible else False if args.headless else None
    result = run_local_validation(
        LocalRunConfig(
            artifact_root=args.artifact_root,
            iterations=args.iterations,
            episode_ids=tuple(args.episodes or ()),
            visible=visible,
            viewer_speed=args.viewer_speed,
            run_id=args.run_id,
        )
    )
    print(f"local validation run: {result.run_id}")
    print(f"manifest: {result.manifest_path}")
    print(f"report: {result.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

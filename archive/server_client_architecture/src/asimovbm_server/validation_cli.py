"""Ergonomic CLI surface for server-local validation runs."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from asimovbm_server.agents import default_agent_registry
from asimovbm_server.benchmarks import (
    BenchmarkRunConfig,
    EpisodicValidationRunner,
    write_result_json,
)
from asimovbm_server.episodes import EpisodePack, load_episode_pack
from asimovbm_server.robots import default_robot_registry

logger = logging.getLogger("asimovbm.server")

DEFAULT_PACK = Path("examples/episode_packs/social_navigation_mvp.json")
PACK_ALIASES = {
    "social": DEFAULT_PACK,
    "social_navigation_mvp": DEFAULT_PACK,
    "robojudo": Path("examples/episode_packs/robojudo_navigation_validation.json"),
    "robojudo_navigation_validation": Path(
        "examples/episode_packs/robojudo_navigation_validation.json"
    ),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="asimovbm-server local-validation",
        description="Server-local episode validation commands.",
    )
    parser.add_argument("--episode-pack", type=Path, default=DEFAULT_PACK)
    parser.add_argument("--artifact-root", type=Path, default=Path("./artifacts"))
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List validation resources.")
    list_parser.add_argument("resource", choices=("packs", "episodes", "tiers", "robots", "agents"))
    list_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    run_parser = subparsers.add_parser("run", help="Run one selected episode.")
    _add_run_flags(run_parser)
    run_parser.add_argument("--artifact-root", type=Path, default=Path("./artifacts"))
    run_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    matrix_parser = subparsers.add_parser("matrix", help="Run robot/episode matrix validation.")
    _add_run_flags(matrix_parser, include_robot=False)
    matrix_parser.add_argument("--artifact-root", type=Path, default=Path("./artifacts"))
    matrix_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    matrix_parser.add_argument(
        "--robot-profile",
        action="append",
        dest="robot_profiles",
        default=[],
        help="Robot profile id. Repeat for a matrix.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    pack_path = _resolve_episode_pack(args.episode_pack)
    pack = load_episode_pack(pack_path)

    if args.command == "list":
        payload = _list_payload(args.resource, pack)
        _emit(payload, json_output=args.json)
        return 0

    args.artifact_root.mkdir(parents=True, exist_ok=True)
    if hasattr(args, "robot_profiles"):
        robot_profiles = tuple(args.robot_profiles or ["minimal-mobile-base"])
    else:
        robot_profiles = (args.robot_profile,)
    result = EpisodicValidationRunner().run(
        pack,
        BenchmarkRunConfig(
            robot_profile_id=robot_profiles[0],
            robot_profile_ids=robot_profiles,
            agent_id=args.agent_profile,
            visible=args.visible,
            realtime=args.realtime,
            tier_id=args.tier_id,
            episode_id=args.episode_id,
        ),
    )
    output_path = args.artifact_root / f"{pack.id}-validation-result.json"
    write_result_json(result, output_path)
    payload = {
        "pack_id": result.pack_id,
        "attempts": result.attempts,
        "valid_episodes": result.valid_episodes,
        "result_path": str(output_path),
        "records": [
            {
                "tier_id": record.tier_id,
                "episode_id": record.episode_id,
                "robot_profile_id": record.robot_profile_id,
                "status": record.trace.terminal_status.code,
                "technical_valid": record.trace.technical_valid,
            }
            for record in result.records
        ],
    }
    _emit(payload, json_output=args.json)
    logger.info("Local validation complete: result=%s", output_path)
    return 0


def _add_run_flags(parser: argparse.ArgumentParser, *, include_robot: bool = True) -> None:
    parser.add_argument("--tier-id", default=None)
    parser.add_argument("--episode-id", default=None)
    if include_robot:
        parser.add_argument("--robot-profile", default="minimal-mobile-base")
    parser.add_argument("--agent-profile", default="obstacle-aware-nav")
    parser.add_argument("--visible", action="store_true")
    parser.add_argument("--realtime", type=float, default=0.0)


def _list_payload(resource: str, pack: EpisodePack) -> dict[str, object]:
    if resource == "packs":
        return {
            "packs": [
                {"id": pack.id, "version": pack.version, "selected": True},
                *[
                    {"id": alias, "path": str(path), "selected": False}
                    for alias, path in PACK_ALIASES.items()
                    if alias != pack.id
                ],
            ]
        }
    if resource == "robots":
        return {"robots": [profile.setup_metadata() for profile in default_robot_registry().profiles()]}
    if resource == "agents":
        return {"agents": list(default_agent_registry().agent_ids())}
    if resource == "tiers":
        return {"tiers": [{"id": tier.id, "episode_count": len(tier.episodes)} for tier in pack.tiers]}
    return {
        "episodes": [
            {
                "tier_id": tier.id,
                "episode_id": episode.id,
                "scenario_type": episode.scenario_type,
            }
            for tier in pack.tiers
            for episode in tier.episodes
        ]
    }


def _emit(payload: dict[str, object], *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(payload, indent=2, default=str))
        return
    for key, value in payload.items():
        print(f"{key}: {value}")


def _resolve_episode_pack(value: Path) -> Path:
    return PACK_ALIASES.get(str(value), value)

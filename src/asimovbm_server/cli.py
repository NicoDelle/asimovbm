"""``asimovbm-server`` CLI entry point."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import uvicorn

from .app import create_app
from .config import ServerConfig

logger = logging.getLogger("asimovbm.server")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="asimovbm-server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--bootstrap-token",
        default=None,
        help="Admin/bootstrap token. If omitted, a fresh random token is generated and printed.",
    )
    parser.add_argument(
        "--artifact-root",
        type=Path,
        default=Path("./artifacts"),
        help="Directory for per-run artifact output.",
    )
    parser.add_argument(
        "--disable-loopback-bootstrap",
        action="store_true",
        help="Require the bootstrap token even from 127.0.0.1.",
    )
    parser.add_argument("--log-level", default="info")
    return parser


def _redacted_log_value(token: str) -> str:
    if len(token) <= 8:
        return "<redacted>"
    return f"{token[:4]}...{token[-4:]}"


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=args.log_level.upper())

    bootstrap_token = args.bootstrap_token
    if not bootstrap_token:
        config = ServerConfig.from_env(artifact_root=args.artifact_root)
        bootstrap_token = config.bootstrap_token
        logger.warning(
            "Bootstrap token not provided. Generated one (redacted=%s). "
            "Use --bootstrap-token to supply your own.",
            _redacted_log_value(bootstrap_token),
        )

    config = ServerConfig(
        bootstrap_token=bootstrap_token,
        artifact_root=args.artifact_root,
        allow_loopback_session_creation=not args.disable_loopback_bootstrap,
    )
    args.artifact_root.mkdir(parents=True, exist_ok=True)
    app = create_app(config)

    uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

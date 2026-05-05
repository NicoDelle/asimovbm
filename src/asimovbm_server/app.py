"""FastAPI application factory."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from .api import package_routes, report_routes, session_routes, websocket_routes
from .api.websocket_routes import EchoOrchestrator, EpisodeOrchestrator
from .config import ServerConfig
from .sessions import SessionManager


def create_app(
    config: ServerConfig,
    *,
    session_manager: SessionManager | None = None,
    orchestrator: EpisodeOrchestrator | None = None,
    reports: dict[str, dict[str, Any]] | None = None,
) -> FastAPI:
    app = FastAPI(title="Asimov Benchmark Server", version="0.1.0")
    app.state.config = config
    app.state.session_manager = session_manager or SessionManager(config)
    app.state.orchestrator = orchestrator or EchoOrchestrator()
    app.state.reports = reports if reports is not None else {}

    app.include_router(session_routes.router)
    app.include_router(package_routes.router)
    app.include_router(report_routes.router)
    app.include_router(websocket_routes.router)

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok", "protocol": "asimovbm.client.v0"}

    return app

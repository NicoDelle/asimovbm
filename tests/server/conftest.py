"""Shared fixtures for server tests."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fastapi.testclient import TestClient

from asimovbm_server import ServerConfig, SessionManager, create_app

BOOTSTRAP_TOKEN = "test-bootstrap-token"


@pytest.fixture()
def artifact_root() -> Iterator[Path]:
    with TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture()
def config(artifact_root: Path) -> ServerConfig:
    return ServerConfig(
        bootstrap_token=BOOTSTRAP_TOKEN,
        artifact_root=artifact_root,
        max_sessions=4,
        max_message_bytes=1024,
        max_invalid_messages=3,
        session_idle_timeout_s=60.0,
        terminal_grace_s=60.0,
        allow_loopback_session_creation=False,
    )


@pytest.fixture()
def manager(config: ServerConfig) -> SessionManager:
    return SessionManager(config)


@pytest.fixture()
def app(config: ServerConfig, manager: SessionManager):
    return create_app(config, session_manager=manager)


@pytest.fixture()
def client(app):
    with TestClient(app) as test_client:
        yield test_client

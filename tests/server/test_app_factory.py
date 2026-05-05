"""App factory + health route smoke."""

from __future__ import annotations


def test_health_route_returns_protocol_version(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["protocol"] == "asimovbm.client.v0"


def test_app_registers_expected_routes(app) -> None:
    paths = {route.path for route in app.routes}
    expected_subpaths = [
        "/health",
        "/sessions",
        "/sessions/{run_id}",
        "/sessions/{run_id}/package",
        "/sessions/{run_id}/control",
    ]
    for sub in expected_subpaths:
        assert any(sub in path for path in paths), f"missing route: {sub}"

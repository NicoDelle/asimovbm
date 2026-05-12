"""Report retrieval route tests."""

from __future__ import annotations

from .conftest import BOOTSTRAP_TOKEN


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_session(client) -> dict[str, str]:
    return client.post(
        "/sessions", json={}, headers=_bearer(BOOTSTRAP_TOKEN)
    ).json()


def test_report_retrieval_requires_run_token(client, app, manager) -> None:
    sess = _create_session(client)
    session = manager._sessions[sess["run_id"]]
    report_ref = manager.make_report_ref()
    manager.finalize(session, report_ref=report_ref)
    app.state.reports[report_ref] = {"status": "ok", "maturity": "fake_protocol"}

    no_auth = client.get(f"/reports/{report_ref}")
    assert no_auth.status_code == 401

    wrong_auth = client.get(
        f"/reports/{report_ref}", headers=_bearer("wrong")
    )
    assert wrong_auth.status_code == 401

    correct = client.get(
        f"/reports/{report_ref}", headers=_bearer(sess["run_token"])
    )
    assert correct.status_code == 200
    payload = correct.json()
    assert payload["status"] == "ok"
    assert payload["maturity"] == "fake_protocol"


def test_report_ref_does_not_expose_filesystem_paths(manager) -> None:
    refs = {manager.make_report_ref() for _ in range(50)}
    for ref in refs:
        assert ref.startswith("srv://reports/")
        # No filesystem-looking substrings.
        assert "/tmp" not in ref
        assert "artifacts" not in ref
        assert ".." not in ref


def test_unknown_report_ref_returns_404(client) -> None:
    sess = _create_session(client)
    response = client.get(
        "/reports/srv://reports/does-not-exist",
        headers=_bearer(sess["run_token"]),
    )
    assert response.status_code in {401, 404}


def test_other_session_token_cannot_retrieve_report(client, app, manager) -> None:
    owner = _create_session(client)
    intruder = _create_session(client)
    owner_session = manager._sessions[owner["run_id"]]
    report_ref = manager.make_report_ref()
    manager.finalize(owner_session, report_ref=report_ref)
    app.state.reports[report_ref] = {"status": "ok"}

    response = client.get(
        f"/reports/{report_ref}",
        headers=_bearer(intruder["run_token"]),
    )
    assert response.status_code == 401

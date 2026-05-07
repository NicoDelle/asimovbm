from __future__ import annotations

from pathlib import Path


def test_local_validation_modules_do_not_import_client_transport() -> None:
    roots = [
        Path("src/asimovbm_server/benchmarks"),
        Path("src/asimovbm_server/episodes"),
        Path("src/asimovbm_server/agents"),
        Path("src/asimovbm_server/robots"),
        Path("src/asimovbm_server/traces"),
        Path("src/asimovbm_server/metrics"),
    ]

    offenders = []
    for root in roots:
        for path in root.rglob("*.py"):
            if "asimovbm_client" in path.read_text(encoding="utf-8"):
                offenders.append(str(path))

    assert offenders == []

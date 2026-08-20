from __future__ import annotations

import json

from asimovbm.local_runner.artifacts import write_json


def test_write_json_normalizes_bytes_in_nested_payloads(tmp_path) -> None:
    path = tmp_path / "trace.json"

    write_json(path, {"metadata": {"stderr_tail": b"viewer bytes"}})

    assert json.loads(path.read_text(encoding="utf-8")) == {
        "metadata": {"stderr_tail": "viewer bytes"}
    }

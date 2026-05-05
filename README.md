# Asimov Benchmark

Paper HRI benchmark artifacts. Two packages:

- `asimovbm_client`: headless Python client. Runs participant policy code
  locally and exchanges step/action messages with the benchmark server.
- `asimovbm_server`: FastAPI/Uvicorn server. Owns authoritative simulation,
  package validation, episode state, telemetry, metrics, and reports.

Shared message contract lives in `asimovbm_protocol`.

## Install

Editable install with extras:

```bash
pip install -e .[server,client-transport,dev]
```

Optional extras:

- `server`: FastAPI, Uvicorn, Pydantic, websockets (server runtime).
- `client-transport`: websockets sync client (real client transport).
- `g1-mujoco`: MuJoCo and ONNX runtime for optional `g1_slam` visualization
  and locomotion paths. Pure-Python `g1_slam` smoke needs no extras.
- `dev`: pytest, httpx, ruff.

## Demos

Four demo labels, each proves a different layer:

| Demo | Proves |
|---|---|
| Fake protocol demo | Client message lifecycle and compatibility. |
| Server transport demo | WebSocket transport carries the same lifecycle. |
| `g1_slam` batch smoke | Real navigation telemetry ingestion. |
| `g1_slam` policy-in-loop smoke | One real server/client/simulation step. |

Full social-navigation benchmark validity requires metric calibration and
social-tier scenarios beyond this repo's current scope.

### Fake protocol demo

```bash
python -m asimovbm_client.cli \
  --server fake://local \
  --run-token demo-run \
  --robot-package examples/robot_packages/minimal \
  --transformer examples.policies.sample_policy:SampleTransformer \
  --policy examples.policies.sample_policy:SamplePolicy \
  --diagnostics
```

The fake backend is executable documentation. It does not simulate physics,
render scenes, compute calibrated scores, or validate packages with backend
authority.

### Server

Run the local development server:

```bash
asimovbm-server --host 127.0.0.1 --port 8765
```

Then point the client at it:

```bash
asimovbm-client \
  --server ws://127.0.0.1:8765 \
  --run-token <run-token-from-bootstrap> \
  --robot-package examples/robot_packages/minimal \
  --transformer examples.policies.sample_policy:SampleTransformer \
  --policy examples.policies.sample_policy:SamplePolicy
```

## Trust Boundary

Participant transformer code, policy code, model weights, and ML dependencies
run locally. The client sends robot package metadata, actions, and technical
telemetry to the server. The server sends raw named sensor streams and
structured task events, not precomputed policy observations or hidden scores.

Technical failures (setup/import, package validation rejection, policy
exception, invalid action, timeout, disconnect, protocol mismatch) are
distinct from behavioral metric outcomes.

## Protocol

Shared messages live in `asimovbm_protocol`. The client also re-exports them
from `asimovbm_client.protocol` for backwards compatibility. Protocol version
identifier: `asimovbm.client.v0`.

See `docs/protocol/client-server-api.md` and
`docs/protocol/message-lifecycle.md`.

## Tests

```bash
pytest
```

`pytest` picks up both `src/` and `g1_slam/src/` via `pyproject.toml`'s
`pythonpath` setting, so package imports work without manual `PYTHONPATH`.

## Layout

```
src/asimovbm_client/    # Existing headless client.
src/asimovbm_protocol/  # Shared message contract.
src/asimovbm_server/    # FastAPI server, simulation adapters, metrics, reports.
g1_slam/                # Pure-Python navigation demo + optional MuJoCo paths.
docs/                   # Protocol, client, server, and metric specs.
examples/               # Sample policies and robot packages.
tests/                  # Unit and integration tests.
```

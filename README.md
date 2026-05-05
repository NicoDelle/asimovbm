# Asimov Benchmark Client

This repository contains Paper HRI benchmark artifacts. The `asimovbm_client`
package is a headless Python client for running participant policy code locally
while a benchmark server owns simulation, validation, scoring, rendering, and
final reports.

## Quickstart

Run the sample policy against the local fake backend:

```bash
PYTHONPATH=src:. python -m asimovbm_client.cli \
  --server fake://local \
  --run-token demo-run \
  --robot-package examples/robot_packages/minimal \
  --transformer examples.policies.sample_policy:SampleTransformer \
  --policy examples.policies.sample_policy:SamplePolicy \
  --diagnostics
```

The fake backend is executable documentation for the client-facing protocol. It
does not simulate physics, render scenes, compute scores, or validate packages
with backend authority.

## Trust Boundary

Participant transformer code, policy code, model weights, and ML dependencies
run locally. The client sends robot package metadata, actions, and technical
telemetry to the server. The server sends raw named sensor streams and
structured task events, not precomputed policy observations or hidden scores.

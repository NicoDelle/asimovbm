# Asimov Benchmark

Local-first Paper HRI validation artifacts.

The active submission path is `asimovbm-local`: it loads the canonical
`g1_slam` episode configs for one selected robot and policy, executes them
sequentially, records per-step traces, invokes the social-navigation metric
library, and writes reviewer-facing JSON artifacts.

## Install

Editable install with development tools:

```bash
.venv/bin/python -m pip install -e .[dev]
```

Optional MuJoCo/ONNX dependencies for visual and policy-backed `g1_slam` work:

```bash
.venv/bin/python -m pip install -e .[g1-mujoco]
```

## Run Local Validation

Run the G1 canonical episodes once with the default G1 RoboJuDo policy. One
iteration uses visible validation mode by default:

```bash
.venv/bin/asimovbm-local --robot g1 --iterations 1
```

Run the Go2 canonical episodes once with the default Go2 ONNX policy:

```bash
.venv/bin/asimovbm-local --robot go2 --iterations 1
```

Run repeated metric collection headlessly:

```bash
.venv/bin/asimovbm-local --robot g1 --iterations 3 --headless
```

Select an explicit policy profile, or keep the profile defaults and point at a
local policy file:

```bash
.venv/bin/asimovbm-local --robot go2 --policy go2_unitree_rl_mjlab --iterations 1
.venv/bin/asimovbm-local --robot go2 --policy-path policies/go2/my-policy.onnx --iterations 1
```

Run one selected episode for the selected robot:

```bash
.venv/bin/asimovbm-local --robot g1 --episode g1_approach_user --iterations 1
```

Artifacts are written under `artifacts/local-validation/<run-id>/`:

- `manifest.json`: selected robot and policy, selected episodes, config
  checksums, robot/backend selectors, viewer mode, trace paths, metric paths,
  and backend proof metadata.
- `report.json`: run-level technical reliability and per-episode behavioral
  metric blocks.
- `<episode>/iteration-XXX/trace.json`: per-step measurements.
- `<episode>/iteration-XXX/metrics.json`: metric outputs for that trace.

## Canonical Episodes

The local catalog is exactly the six JSON files under
`g1_slam/config/episodes/`:

- `g1_approach_user`
- `g1_lateral_open`
- `g1_lateral_static_dynamic_obstacles`
- `go2_approach_user`
- `go2_lateral_open`
- `go2_lateral_static_dynamic_obstacles`

The catalog preserves each config's start, goal, step count, world, controller,
locomotion, dynamic obstacle, camera, and visualization settings. The active
runner selects one robot per run and records the policy profile used for that
testbench run.

## Metrics

Metric implementations live in `src/asimovbm/metrics/`. They are pure functions
with typed inputs and literature citations in each metric file. The local trace
bridge in `src/asimovbm/local_runner/metrics_bridge.py` extracts the available
inputs and returns `not_applicable` or `insufficient_evidence` when a metric
cannot honestly be computed from the six `g1_slam` traces.

## Tests

```bash
.venv/bin/python -m pytest
```

The active tests cover the local runner, metric library, reports, package
imports, and `g1_slam` pure-Python imports.

## Layout

```text
src/asimovbm/                 # Active local runner, metrics, reports.
g1_slam/                      # Canonical episode configs and navigation code.
docs/specs/                   # Social-navigation metric specification.
docs/plans/                   # Current planning and research notes.
tests/local_runner/           # Local validation tests.
tests/metrics/                # Pure metric library tests.
```

# AsimovBM Local Simulation Runner

This package contains the active local runner for Paper HRI validation. It
loads the six canonical `g1_slam/config/episodes/*.json` episode configs,
runs them sequentially, records step traces, computes the available
social-navigation metrics, and writes JSON artifacts for inspection.

Run every command below from the repository root.

## Install

For normal development, install the package in editable mode:

```bash
pip install -e .[dev]
```

The installed command is:

```bash
asimovbm-local --help
```

If you do not want to install the package yet, use the module entry point with
the repository paths:

```bash
PYTHONPATH=src:g1_slam/src python3 -m asimovbm.local_runner.cli --help
```

## Run One Visible Simulation

One iteration defaults to visible validation mode:

```bash
asimovbm-local --iterations 1
```

To run only one canonical episode:

```bash
asimovbm-local --episode g1_approach_user --iterations 1
```

The visible path requests the canonical robot viewer for the selected episode.
If optional RoboJuDo, MuJoCo, or policy assets are not installed, the run still
records the portable local trace and marks the trace metadata with
`viewer_status: not_launched`.

## Run Headless Metric Collection

Repeated runs default to headless metric collection:

```bash
asimovbm-local --iterations 3
```

You can also force headless mode explicitly:

```bash
asimovbm-local --iterations 3 --headless
```

Headless mode is the preferred path for collecting metric traces because it
does not require visual assets and writes the same metrics/report artifacts.

## Choose Measurement Source

The default measurement source is the portable reference trace:

```bash
asimovbm-local --measurement-backend reference --iterations 1 --headless
```

This path records `measurement_proof_level: reference` and validates that each
sample uses one post-step timestamp for robot state and scenario entities.

The explicit MuJoCo selector is available for proof-gated runs:

```bash
asimovbm-local --measurement-backend mujoco --episode g1_approach_user --headless
```

Until asset-backed MuJoCo trace execution is wired in, that selector reports a
technical measurement failure instead of producing behavioral scores from
incomplete data. Optional MuJoCo helper tests use fake model/data fixtures by
default and can use minimal MJCF scenes when the `mujoco` package is installed.

## Select Episodes

The available episode ids are:

```text
g1_approach_user
g1_lateral_open
g1_lateral_static_dynamic_obstacles
go2_approach_user
go2_lateral_open
go2_lateral_static_dynamic_obstacles
```

Pass `--episode` more than once to run a subset:

```bash
asimovbm-local \
  --episode g1_approach_user \
  --episode go2_lateral_open \
  --iterations 2 \
  --headless
```

## Choose Artifact Output

By default, artifacts are written under:

```text
artifacts/local-validation/<run-id>/
```

Use `--artifact-root` and `--run-id` for stable output paths:

```bash
asimovbm-local \
  --iterations 2 \
  --headless \
  --artifact-root /tmp/asimovbm-local \
  --run-id smoke
```

That command writes:

```text
/tmp/asimovbm-local/smoke/manifest.json
/tmp/asimovbm-local/smoke/report.json
/tmp/asimovbm-local/smoke/<episode-id>/iteration-000/trace.json
/tmp/asimovbm-local/smoke/<episode-id>/iteration-000/metrics.json
```

For multiple iterations, each episode gets `iteration-000`, `iteration-001`,
and so on.

## What The Files Mean

- `manifest.json` records selected episodes, config checksums, robot selectors,
  execution mode, trace paths, metric paths, backend proof metadata,
  `measurement_backend`, and per-record `measurement_proof_level`.
- `report.json` records run-level reliability plus the behavioral metric blocks
  computed from the traces.
- `trace.json` records per-step measurements: time, pose, velocity, action,
  lidar ranges, entity state, collisions, public observation, measurement
  source/proof fields, validation summary, and status.
- `metrics.json` records the metric outputs computed from one episode trace,
  including raw-input summaries for the trace streams each metric consumed.

## Inspect Measurement Traces

Use `trace.json` for measurement-level review. The important fields are:

- `measurement_proof_level`: `unavailable`, `reference`, `fake_model_data`,
  `minimal_mujoco`, or `asset_mujoco`.
- `validation_summary`: monotonic-time, finite-state, proof-level, and
  public-observation leakage checks.
- `steps[].measurement_source`: source used for that sample.
- `steps[].robot_state`: semantic world-frame pose and velocity values used by
  metrics.
- `steps[].qpos` / `steps[].qvel`: raw generalized state when available.
- `steps[].dynamic_entities`: humans, bystanders, targets, and obstacles at the
  same timestamp as the recorded robot pose.
- `steps[].contacts` and `steps[].sensors`: MuJoCo-derived contact and sensor
  slices when available.

Use `metrics.json` to verify metric inputs. Human-safety metrics compute only
when human entities are present; cue/facing-dependent social metrics remain
`not_applicable` with an explicit missing-stream reason until those streams are
available.

## Smoke-Tested Commands

These commands were tested locally from the repository root:

```bash
asimovbm-local \
  --episode g1_approach_user \
  --iterations 1 \
  --headless \
  --artifact-root /tmp/asimovbm-readme-installed \
  --run-id installed-smoke

PYTHONPATH=src:g1_slam/src python3 -m asimovbm.local_runner.cli \
  --episode g1_approach_user \
  --iterations 1 \
  --artifact-root /tmp/asimovbm-readme-visible \
  --run-id visible-smoke

PYTHONPATH=src:g1_slam/src python3 -m asimovbm.local_runner.cli \
  --iterations 2 \
  --headless \
  --measurement-backend reference \
  --artifact-root /tmp/asimovbm-readme-headless \
  --run-id headless-smoke
```

The one-episode commands produced one trace and one metrics file for
`g1_approach_user`. The all-episode command produced traces and metrics for all
six episodes across two iterations.

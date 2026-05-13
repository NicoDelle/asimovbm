# AsimovBM Local Simulation Runner

This package contains the active local runner for Paper HRI validation. It
loads the canonical `g1_slam/config/episodes/*.json` episode configs for one
selected robot and policy, runs them sequentially, records step traces, computes
the available social-navigation metrics, and writes JSON artifacts for
inspection.

Run every command below from the repository root.

## Install

For normal development, install the package in editable mode:

```bash
.venv/bin/python -m pip install -e .[dev]
```

The installed command is:

```bash
.venv/bin/asimovbm-local --help
```

If you do not want to install the package yet, use the module entry point with
the repository paths:

```bash
PYTHONPATH=src:g1_slam/src .venv/bin/python -m asimovbm.local_runner.cli --help
```

## Run One Visible Simulation

One iteration defaults to visible validation mode:

```bash
.venv/bin/asimovbm-local --robot g1 --iterations 1
```

To run only one canonical episode:

```bash
.venv/bin/asimovbm-local --robot g1 --episode g1_approach_user --iterations 1
```

The visible path requests the canonical robot viewer for the selected episode.
If optional RoboJuDo, MuJoCo, or policy assets are not installed, the run still
records the portable local trace and marks the trace metadata with
`viewer_status: not_launched`.

## Run Headless Metric Collection

Repeated runs default to headless metric collection:

```bash
.venv/bin/asimovbm-local --robot g1 --iterations 3
```

You can also force headless mode explicitly:

```bash
.venv/bin/asimovbm-local --robot g1 --iterations 3 --headless
```

Headless mode is the preferred path for collecting metric traces because it
does not require visual assets and writes the same metrics/report artifacts.

## Select Robot, Policy, And Episodes

Every run is scoped to one robot and one policy. The default policy profiles
are:

```text
g1  -> g1_robojudo_asap
go2 -> go2_unitree_rl_mjlab
```

Run all canonical scenarios for one robot:

```bash
.venv/bin/asimovbm-local --robot g1 --iterations 1
.venv/bin/asimovbm-local --robot go2 --iterations 1
```

Override the policy profile or only the local policy file path:

```bash
.venv/bin/asimovbm-local --robot go2 --policy go2_unitree_rl_mjlab --iterations 1
.venv/bin/asimovbm-local --robot go2 --policy-path policies/go2/my-policy.onnx --iterations 1
```

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
.venv/bin/asimovbm-local \
  --robot g1 \
  --episode g1_approach_user \
  --episode g1_lateral_open \
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
.venv/bin/asimovbm-local \
  --robot g1 \
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

## Unity Trace Ingest

Unity is a separate visual validation producer. From WSL, run:

```bash
PYTHONPATH=src:g1_slam/src python -m asimovbm.local_runner.unity_runner run \
  --unity-project /mnt/d/_PROJECTS/Unity/AsimovBM \
  --run-id unity-smoke
```

That command writes `artifacts/unity-validation/<run-id>/manifest.json`,
`report.json`, and one trace/metrics pair per Unity scene.

## What The Files Mean

- `manifest.json` records the selected robot and policy, selected episodes,
  config checksums, robot selectors, execution mode, trace paths, metric paths,
  and backend proof metadata.
- `report.json` records run-level reliability plus the behavioral metric blocks
  computed from the traces.
- `trace.json` records per-step measurements: time, pose, velocity, action,
  lidar ranges, entity state, collisions, public observation, and status.
- `metrics.json` records the metric outputs computed from one episode trace.

## Smoke-Tested Commands

These commands were tested locally from the repository root:

```bash
.venv/bin/asimovbm-local \
  --robot g1 \
  --episode g1_approach_user \
  --iterations 1 \
  --headless \
  --artifact-root /tmp/asimovbm-readme-installed \
  --run-id installed-smoke

PYTHONPATH=src:g1_slam/src .venv/bin/python -m asimovbm.local_runner.cli \
  --robot g1 \
  --episode g1_approach_user \
  --iterations 1 \
  --artifact-root /tmp/asimovbm-readme-visible \
  --run-id visible-smoke

PYTHONPATH=src:g1_slam/src .venv/bin/python -m asimovbm.local_runner.cli \
  --robot g1 \
  --iterations 2 \
  --headless \
  --artifact-root /tmp/asimovbm-readme-headless \
  --run-id headless-smoke
```

The one-episode commands produced one trace and one metrics file for
`g1_approach_user`. The all-scenario command produced traces and metrics for
the three selected G1 episodes across two iterations.

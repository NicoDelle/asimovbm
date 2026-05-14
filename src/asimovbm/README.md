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
.venv/bin/asimovbm-local --robot g1 --episode g1_point_to_point_open --iterations 1
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

For the two G1 RoboJuDo survey-video policies, use
`--policy g1_robojudo_unitree` for RoboJuDo `g1` / survey `policy_a`,
or `--policy g1_robojudo_asap` for RoboJuDo `g1_asap_loco` / survey
`policy_b`.

Run all canonical scenarios for one robot:

```bash
.venv/bin/asimovbm-local --robot g1 --iterations 1
.venv/bin/asimovbm-local --robot go2 --iterations 1
```

Override the policy profile or only the local policy file path:

```bash
.venv/bin/asimovbm-local --robot g1 --policy g1_robojudo_unitree --iterations 1
.venv/bin/asimovbm-local --robot go2 --policy go2_unitree_rl_mjlab --iterations 1
.venv/bin/asimovbm-local --robot go2 --policy-path policies/go2/my-policy.onnx --iterations 1
```

The available episode ids are:

```text
g1_point_to_point_open
g1_point_to_point_static_obstacles
g1_point_to_point_dynamic_npcs
go2_point_to_point_open
go2_point_to_point_static_obstacles
go2_point_to_point_dynamic_npcs
```

Pass `--episode` more than once to run a subset:

```bash
.venv/bin/asimovbm-local \
  --robot g1 \
  --episode g1_point_to_point_open \
  --episode g1_point_to_point_dynamic_npcs \
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
/tmp/asimovbm-local/smoke/episode-metrics-<NNN>.csv
/tmp/asimovbm-local/smoke/<episode-id>/iteration-000/trace.json
/tmp/asimovbm-local/smoke/<episode-id>/iteration-000/metrics.json
```

For multiple iterations, each episode gets `iteration-000`, `iteration-001`,
and so on.

The `episode-metrics-<NNN>.csv` file is the spreadsheet-friendly benchmark
export for the run. It has one row per episode iteration, metadata columns
(`run_id`, `episode_id`, `iteration`, status fields), the four macro axes, and
the current social-navigation submetrics. Score cells are normalized `[0, 1]`;
empty cells mean unavailable or not applicable, not zero. The detailed status,
confidence, raw values, and reasons remain in `metrics.json` and `report.json`.

## Export Survey Videos

Add `--survey-export` to render one direct MuJoCo MP4 per selected episode for
each survey view (`arrival` and `bystander` by default). The exporter writes
MP4/JSON pairs using the survey discovery contract plus a metric summary:

```bash
.venv/bin/asimovbm-local \
  --robot g1 \
  --survey-export \
  --survey-policy-id policy_a \
  --survey-root artifacts/survey \
  --iterations 1
```

Defaults are browser-compatible H.264 MP4 clips at `1280x720`, `24fps`, and a
15-second duration cap. Tune them with `--survey-video-width`,
`--survey-video-height`, `--survey-video-fps`, and `--survey-video-max-duration
0` when you need full-duration exports.

Outputs:

```text
artifacts/survey/videos/<policy>/<view>/<episode>.mp4
artifacts/survey/json/<policy>/<view>/<episode>.json
artifacts/survey/metrics-summary-<run-id>.json
artifacts/survey/metrics-summary-<run-id>.csv
```

## What The Files Mean

- `manifest.json` records the selected robot and policy, selected episodes,
  config checksums, robot selectors, execution mode, trace paths, metric paths,
  and backend proof metadata.
- `report.json` records run-level reliability plus the behavioral metric blocks
  computed from the traces.
- `episode-metrics-<NNN>.csv` records one compact benchmark row per episode
  iteration for spreadsheets and web prediction lookups.
- `trace.json` records per-step measurements: time, pose, velocity, action,
  lidar ranges, entity state, collisions, public observation, and status.
- `metrics.json` records the metric outputs computed from one episode trace.

## Smoke-Tested Commands

These commands were tested locally from the repository root:

```bash
.venv/bin/asimovbm-local \
  --robot g1 \
  --episode g1_point_to_point_open \
  --iterations 1 \
  --headless \
  --artifact-root /tmp/asimovbm-readme-installed \
  --run-id installed-smoke

PYTHONPATH=src:g1_slam/src .venv/bin/python -m asimovbm.local_runner.cli \
  --robot g1 \
  --episode g1_point_to_point_open \
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
`g1_point_to_point_open`. The all-scenario command produced traces and metrics
for the three selected G1 episodes across two iterations.

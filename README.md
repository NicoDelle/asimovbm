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

Run the selected robot/policy and export direct MuJoCo-rendered survey videos
plus metric sidecars:

```bash
.venv/bin/asimovbm-local \
  --robot g1 \
  --policy g1_robojudo_asap \
  --survey-export \
  --survey-policy-id policy_a \
  --survey-root artifacts/survey \
  --iterations 1
```

The default survey render is a bounded `426x240`, `2fps`, 15-second time-lapse
so a full robot run completes without turning the export phase into a silent
slog. Use `--survey-video-width`, `--survey-video-height`,
`--survey-video-fps`, and `--survey-video-max-duration 0` for full-duration,
higher-fidelity exports.

Artifacts are written under `artifacts/local-validation/<run-id>/`:

- `manifest.json`: selected robot and policy, selected episodes, config
  checksums, robot/backend selectors, viewer mode, trace paths, metric paths,
  and backend proof metadata.
- `report.json`: run-level technical reliability and per-episode behavioral
  metric blocks.
- `episode-metrics-XXX.csv`: one row per episode run with metadata, four axis
  scores, and normalized metric scores for spreadsheet and survey comparison
  workflows.
- With `--survey-export`, survey MP4s are written as
  `artifacts/survey/videos/<policy>/<view>/<episode>.mp4`, matching JSON
  sidecars as `artifacts/survey/json/<policy>/<view>/<episode>.json`, and
  metric summaries as `artifacts/survey/metrics-summary-<run-id>.{json,csv}`.
  The videos are captured from MuJoCo offscreen cameras (`arrival` and
  `bystander` by default), not from reconstructed trace drawings.
- `<episode>/iteration-XXX/trace.json`: per-step measurements.
- `<episode>/iteration-XXX/metrics.json`: metric outputs for that trace.

## Run Unity MuJoCo Validation

Prepare the Windows Unity project from WSL:

```bash
python tools/unity/prepare_mujoco_unity_project.py \
  --unity-project /mnt/d/_PROJECTS/Unity/AsimovBM \
  --package-mode git \
  --stage-real-g1 \
  --skip-dll
```

Then run Unity batchmode validation and ingest Unity JSON traces:

```bash
PYTHONPATH=src:g1_slam/src python -m asimovbm.local_runner.unity_runner run \
  --unity-project /mnt/d/_PROJECTS/Unity/AsimovBM \
  --run-id unity-smoke
```

Artifacts are written under `artifacts/unity-validation/<run-id>/`. The Unity
path currently validates `g1_kinematic_smoke` and `g1_real_motion`, with one raw
Unity trace, normalized trace, and metrics file per scene.

## Run Metrics Dashboard and Survey

Start the local web dashboard over validation artifacts:

```bash
asimovbm-web --artifact-root artifacts/local-validation
```

Open `http://127.0.0.1:8765` to inspect metric runs. To enable the survey
page, provide a video manifest and video root:

```bash
asimovbm-web \
  --artifact-root artifacts/local-validation \
  --survey-root artifacts/survey \
  --video-root artifacts/survey/videos \
  --survey-json-root artifacts/survey/json \
  --study-id pilot
```

The same page can also compare objective predictions from `metrics.json`,
`episode-metrics-XXX.csv`, or trace JSON against survey outcomes. If no
manifest is provided, the server discovers Unity video-generation outputs with
matching stems under `artifacts/survey/videos/<policy>/<view>/<episode>.mp4`
and `artifacts/survey/json/<policy>/<view>/<episode>.json`. Survey responses
use anonymous hard quota-balanced assignment by robot/policy/viewpoint cell and
are written under `artifacts/survey/<study-id>/`:

- `participants.jsonl`: append-only participant/session metadata.
- `responses.jsonl`: append-only per-video Likert responses.
- `participants.csv`: regenerated participant export for spreadsheet tooling.

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
src/asimovbm/web/             # Local metrics dashboard and survey server.
src/asimovbm/survey/          # Survey design, storage, export, and analysis.
g1_slam/                      # Canonical episode configs and navigation code.
docs/specs/                   # Social-navigation metric specification.
docs/plans/                   # Current planning and research notes.
tests/web/                    # Local webserver and artifact-index tests.
tests/survey/                 # Survey design/storage/export/analysis tests.
tests/local_runner/           # Local validation tests.
tests/metrics/                # Pure metric library tests.
```

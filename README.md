# Asimov Benchmark

Local-first Paper HRI validation artifacts.

The active submission path is `asimovbm-local`: it loads the six canonical
`g1_slam` episode configs, executes them sequentially, records per-step traces,
invokes the social-navigation metric library, and writes reviewer-facing JSON
artifacts.

## Install

Editable install with development tools:

```bash
pip install -e .[dev]
```

Optional MuJoCo/ONNX dependencies for visual and policy-backed `g1_slam` work:

```bash
pip install -e .[g1-mujoco]
```

## Run Local Validation

Run all six canonical episodes once. One iteration uses visible validation mode
by default:

```bash
asimovbm-local --iterations 1
```

Run repeated metric collection headlessly:

```bash
asimovbm-local --iterations 3 --headless
```

Run one selected episode:

```bash
asimovbm-local --episode g1_approach_user --iterations 1
```

Artifacts are written under `artifacts/local-validation/<run-id>/`:

- `manifest.json`: selected episodes, config checksums, robot/backend selectors,
  viewer mode, trace paths, metric paths, and backend proof metadata.
- `report.json`: run-level technical reliability and per-episode behavioral
  metric blocks.
- `<episode>/iteration-XXX/trace.json`: per-step measurements.
- `<episode>/iteration-XXX/metrics.json`: metric outputs for that trace.

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
  --video-manifest examples/survey/video_manifest.example.json \
  --study-id pilot
```

Survey responses are written under `artifacts/survey/<study-id>/`:

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
runner chooses only visible/headless mode and artifact location.

## Metrics

Metric implementations live in `src/asimovbm/metrics/`. They are pure functions
with typed inputs and literature citations in each metric file. The local trace
bridge in `src/asimovbm/local_runner/metrics_bridge.py` extracts the available
inputs and returns `not_applicable` or `insufficient_evidence` when a metric
cannot honestly be computed from the six `g1_slam` traces.

## Tests

```bash
pytest
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

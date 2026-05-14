# Asimov Benchmark

Local-first Human-Robot Interaction benchmark validation artifacts for comparing
robot navigation policies with both objective simulation metrics and human survey
responses.

The active path is `asimovbm-local`: it loads canonical `g1_slam` episode
configs for a selected robot and policy, runs them sequentially, records
per-step traces, computes social-navigation metrics, and writes reviewer-facing
artifacts. The local web server then reads those artifacts, serves survey
videos, collects Likert responses, and compares benchmark predictions with
human outcomes.

## Current Status

The core workflow is MuJoCo based. Unity-related code and plans were removed so
the repository now focuses on:

- `g1_slam/`: MuJoCo simulation, canonical episodes, assets, and RoboJuDo /
  Unitree policy integrations.
- `src/asimovbm/local_runner/`: local benchmark runner, artifact generation,
  metrics bridge, and survey video export.
- `src/asimovbm/metrics/`: social-navigation metric implementations.
- `src/asimovbm/reports/`: JSON and CSV report export.
- `src/asimovbm/web/`: metrics dashboard, survey UI, and comparison view.
- `src/asimovbm/survey/`: survey design, storage, prediction, and analysis.
- `artifacts/local-validation/`: benchmark run artifacts.
- `artifacts/survey/`: survey videos, JSON sidecars, and survey responses.

The website can already:

- Read benchmark artifacts and survey data.
- Discover survey videos from the folder contract documented below.
- Show videos in the browser.
- Assign survey groups and collect four Likert answers per video.
- Show benchmark prediction, real survey results, and their difference.
- Link run/episode views to the related videos and metric scores.
- Serve MP4 files with byte-range support for browser playback.

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

Run the G1 canonical episodes once with the default G1 RoboJuDo policy:

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

Run one selected episode:

```bash
.venv/bin/asimovbm-local --robot g1 --episode g1_point_to_point_open --iterations 1
```

## Policies

The two G1 RoboJuDo policies used by the survey-video sweep are:

- `g1_robojudo_unitree`: RoboJuDo config `g1`; this is `policy_a` in survey folders.
- `g1_robojudo_asap`: RoboJuDo config `g1_asap_loco`; this is `policy_b` in survey folders.

Run explicit policies:

```bash
.venv/bin/asimovbm-local --robot g1 --policy g1_robojudo_unitree --iterations 1
.venv/bin/asimovbm-local --robot g1 --policy g1_robojudo_asap --iterations 1
.venv/bin/asimovbm-local --robot go2 --policy go2_unitree_rl_mjlab --iterations 1
.venv/bin/asimovbm-local --robot go2 --policy-path policies/go2/my-policy.onnx --iterations 1
```

Survey labels:

- `policy_a`: RoboJuDo `g1`.
- `policy_b`: RoboJuDo `g1_asap_loco`.
- `asap_loco` is policy B.

## Canonical Episodes

The local catalog is the six JSON files under `g1_slam/config/episodes/`:

- `g1_point_to_point_open`
- `g1_point_to_point_static_obstacles`
- `g1_point_to_point_dynamic_npcs`
- `go2_point_to_point_open`
- `go2_point_to_point_static_obstacles`
- `go2_point_to_point_dynamic_npcs`

For the survey, each policy/view cell should contain the three G1 point-to-point
episodes:

1. `g1_point_to_point_open`: A to B, no obstacles.
2. `g1_point_to_point_static_obstacles`: A to B, fixed obstacles.
3. `g1_point_to_point_dynamic_npcs`: A to B, moving people.

The catalog preserves each config's start, goal, step count, world, controller,
locomotion, dynamic obstacle, camera, and visualization settings. The active
runner selects one robot per run and records the policy profile used for that
testbench run.

## Local Validation Artifacts

Artifacts are written under `artifacts/local-validation/<run-id>/`:

- `manifest.json`: selected robot and policy, selected episodes, config
  checksums, robot/backend selectors, viewer mode, trace paths, metric paths,
  and backend proof metadata.
- `report.json`: run-level technical reliability and per-episode behavioral
  metric blocks.
- `episode-metrics-XXX.csv`: one row per episode run with metadata, four axis
  scores, and normalized metric scores for spreadsheet and survey comparison.
- `<episode>/iteration-XXX/trace.json`: per-step measurements.
- `<episode>/iteration-XXX/metrics.json`: metric outputs for that trace.

The high-level metric axes are:

- `perceived_dexterity`
- `perceived_safety`
- `perceived_social_awareness`
- `impression`

Metric implementations live in `src/asimovbm/metrics/`. They are pure functions
with typed inputs and literature citations in each metric file. The local trace
bridge in `src/asimovbm/local_runner/metrics_bridge.py` extracts available
inputs and returns `not_applicable` or `insufficient_evidence` when a metric
cannot honestly be computed from the available traces.

## Export Survey Videos

Run the selected robot/policy and export direct MuJoCo-rendered survey videos
plus metric sidecars:

```bash
.venv/bin/asimovbm-local \
  --robot g1 \
  --policy g1_robojudo_unitree \
  --survey-export \
  --survey-policy-id policy_a \
  --survey-root artifacts/survey \
  --iterations 1
```

The default survey render is a bounded `426x240`, `2fps`, 15-second time-lapse
so a full robot run completes without making the export phase too slow. Use
`--survey-video-width`, `--survey-video-height`, `--survey-video-fps`, and
`--survey-video-max-duration 0` for full-duration, higher-fidelity exports.

Future exports should use browser-friendly MP4 settings:

- H.264 video codec.
- `yuv420p` pixel format.
- `1280x720` resolution when possible.
- `24fps` when possible.

The survey videos are captured from MuJoCo offscreen cameras, not from
reconstructed trace drawings. The default survey views are:

- `arrival`: first-person/objective viewpoint.
- `bystander`: third-person observer viewpoint.

## Survey Video Folder Contract

The web server can discover survey videos automatically when files are placed
under two parallel roots:

```text
artifacts/survey/videos/
artifacts/survey/json/
```

Start the server with these roots:

```bash
PYTHONPATH=src python -m asimovbm.web.server \
  --artifact-root artifacts/local-validation \
  --survey-root artifacts/survey \
  --video-root artifacts/survey/videos \
  --survey-json-root artifacts/survey/json \
  --study-id pilot
```

Do not pass `--video-manifest` when using this folder contract. The server will
build the manifest from paired video and JSON sidecar files.

Every exported episode must create one MP4 and one JSON sidecar with the same
relative stem:

```text
artifacts/survey/videos/<policy>/<view>/<episode>.mp4
artifacts/survey/json/<policy>/<view>/<episode>.json
```

The `<policy>`, `<view>`, and `<episode>` path parts must match exactly between
the MP4 and JSON paths. Only the root folder and extension differ.

Valid examples:

```text
artifacts/survey/videos/policy_a/arrival/g1_point_to_point_open.mp4
artifacts/survey/json/policy_a/arrival/g1_point_to_point_open.json

artifacts/survey/videos/policy_a/bystander/g1_point_to_point_open.mp4
artifacts/survey/json/policy_a/bystander/g1_point_to_point_open.json

artifacts/survey/videos/policy_b/arrival/g1_point_to_point_static_obstacles.mp4
artifacts/survey/json/policy_b/arrival/g1_point_to_point_static_obstacles.json

artifacts/survey/videos/policy_b/bystander/g1_point_to_point_dynamic_npcs.mp4
artifacts/survey/json/policy_b/bystander/g1_point_to_point_dynamic_npcs.json
```

Invalid examples:

```text
artifacts/survey/videos/policy_a/arrival/scenario.mp4
artifacts/survey/json/policy_a/bystander/scenario.json
```

The view differs, so the JSON is not the sidecar for that MP4.

```text
artifacts/survey/videos/policy_a/arrival/nested/scenario.mp4
```

The MP4 is too deep. Discovery accepts exactly three path parts under the video
root: `<policy>/<view>/<episode>.mp4`.

## Required Survey Export Matrix

For the first survey pass, export four cells:

```text
policy_a/arrival/
policy_a/bystander/
policy_b/arrival/
policy_b/bystander/
```

Each cell should contain the same three scenario stems:

```text
g1_point_to_point_open
g1_point_to_point_static_obstacles
g1_point_to_point_dynamic_npcs
```

That produces 12 MP4 files and 12 matching JSON files.

Go2 files are optional. If exporting Go2, put `robot_id: "go2"` in the JSON and
start the server with `--include-go2`.

## Survey Naming Rules

Use lowercase snake_case for every path component.

Policy folders:

```text
policy_a
policy_b
```

View folders:

```text
arrival
bystander
```

The server maps `arrival` to the survey's first-person viewpoint. It also
understands `fp`, `first_person`, and `firstperson`, but `arrival` is the
preferred export folder.

Episode filename stems:

```text
g1_point_to_point_open
g1_point_to_point_static_obstacles
g1_point_to_point_dynamic_npcs
```

The server uses these suffixes to order the three videos in the survey:

```text
*_point_to_point_open                 -> episode 1
*_point_to_point_static_obstacles     -> episode 2
*_point_to_point_dynamic_npcs         -> episode 3
```

Unknown episode names are still discovered, but they are sorted after the known
three episodes.

## JSON Sidecar Shape

Each JSON sidecar must be a JSON object. The simplest supported shape is:

```json
{
  "schema_version": "asimovbm.simulation_episode.v1",
  "episode_id": "g1_point_to_point_open",
  "robot_id": "g1",
  "policy_id": "policy_a",
  "camera_view": "arrival",
  "metric_report": {
    "behavioral_metrics": {
      "axes": {
        "perceived_dexterity": {"score": 0.82},
        "perceived_safety": {"score": 0.76},
        "perceived_social_awareness": {"score": 0.69},
        "impression": {"score": 0.74}
      }
    },
    "metrics": {}
  }
}
```

Required metadata fields:

```text
episode_id
robot_id
policy_id
camera_view
metric_report.behavioral_metrics.axes
```

Axis IDs:

```text
perceived_dexterity
perceived_safety
perceived_social_awareness
impression
```

Scores may be written on a `0..1` scale or a `0..100` scale. The server converts
`0..1` values to `0..100` automatically.

The metadata fields may also be nested under `metadata` or `render`, but the
top-level fields above are preferred because they are easiest to inspect.

## How The Server Derives Survey Fields

For this file pair:

```text
artifacts/survey/videos/policy_a/arrival/g1_point_to_point_open.mp4
artifacts/survey/json/policy_a/arrival/g1_point_to_point_open.json
```

with:

```json
{
  "episode_id": "g1_point_to_point_open",
  "robot_id": "g1",
  "policy_id": "policy_a",
  "camera_view": "arrival"
}
```

the server derives:

```text
video_id: policy_a_fp_g1_point_to_point_open
policy_id: policy_a
viewpoint: first_person
robot_id: g1
episode_id: g1_point_to_point_open
group_id: policy_a_fp
episode_order: 1
prediction_source: survey_json_root/policy_a/arrival/g1_point_to_point_open.json
```

For bystander files, `group_id` becomes:

```text
policy_a_bystander
policy_b_bystander
```

For Go2 files, the group is prefixed:

```text
go2_policy_a_fp
go2_policy_a_bystander
go2_policy_b_fp
go2_policy_b_bystander
```

## Exporter Checklist

Before the exporter exits, it should verify:

- Every MP4 has a matching JSON sidecar with the same relative stem.
- Every JSON sidecar has a matching MP4 with the same relative stem.
- Every MP4 is exactly under `<policy>/<view>/<episode>.mp4`.
- Every required policy/view cell has exactly three known episodes.
- `policy_id` in JSON matches the policy folder.
- `camera_view` in JSON matches the view folder.
- `episode_id` in JSON matches the episode filename stem.
- `robot_id` is present and is usually `g1`.
- The four axis scores are present under `metric_report.behavioral_metrics.axes`.

If one of these checks fails, fail the export rather than producing a partial
survey folder. Partial folders are hard to debug because the webserver will only
show what it can discover.

## Run Metrics Dashboard And Survey

Start the local web dashboard over validation artifacts:

```bash
asimovbm-web --artifact-root artifacts/local-validation
```

Open `http://127.0.0.1:8765` to inspect metric runs.

Start the dashboard with survey videos and sidecars:

```bash
asimovbm-web \
  --artifact-root artifacts/local-validation \
  --survey-root artifacts/survey \
  --video-root artifacts/survey/videos \
  --survey-json-root artifacts/survey/json \
  --study-id pilot
```

The same page can compare objective predictions from `metrics.json`,
`episode-metrics-XXX.csv`, or trace JSON against survey outcomes. If no manifest
is provided, the server discovers matching stems under:

```text
artifacts/survey/videos/<policy>/<view>/<episode>.mp4
artifacts/survey/json/<policy>/<view>/<episode>.json
```

Survey responses use anonymous hard quota-balanced assignment by
robot/policy/viewpoint cell and are written under `artifacts/survey/<study-id>/`:

- `participants.jsonl`: append-only participant/session metadata.
- `responses.jsonl`: append-only per-video Likert responses.
- `participants.csv`: regenerated participant export for spreadsheet tooling.

## Survey Study Mapping

The current paper/survey notebook uses this video mapping:

| Survey block | Policy | POV | Meaning |
|---|---|---|---|
| Q1 | A | first person | Viewer is the objective/goal of the robot |
| Q2 | B | first person | Viewer is the objective/goal of the robot |
| Q3 | A | third person | Viewer observes the scene |
| Q4 | B | third person | Viewer observes the scene |

Each Q video is a bundle of three episodes: no obstacles, fixed obstacles, and
moving people.

## Analysis Notebooks

The current analysis is split into three notebooks:

- `survey_results.ipynb`: imports and analyzes the human survey data.
- `simulation_results.ipynb`: imports and explores logged simulation metrics.
- `paper_results.ipynb`: imports both sources and checks whether the simulation
  benchmark agrees with survey outcomes.

The mixed notebook compares rankings and paired deltas rather than raw absolute
scores, because the survey uses a `-3..+3` scale while the simulation metrics
use `0..1` normalized scores.

## Manual MuJoCo Validation Shortcut

Use this path when you want to watch the proper MuJoCo/RoboJuDo viewer yourself,
then inspect the freshly computed metrics in the local web dashboard. Do not add
`--survey-export` for this workflow. The important flag is
`--trace-backend real`: without it, `asimovbm-local` uses the portable reference
trace backend for CI-style smoke runs.

Policy A:

```bash
.venv/bin/asimovbm-local \
  --robot g1 \
  --iterations 1 \
  --visible \
  --trace-backend real \
  --policy g1_robojudo_unitree \
  --viewer-speed 1.0 \
  --camera-view arrival \
  --episode-steps 900 \
  --start-delay 1.0 \
  --run-id hand-validated-g1-policy-a
```

Policy mapping for the survey videos:

- policy A: `g1_robojudo_unitree` / RoboJuDo config `g1`
- policy B: `g1_robojudo_asap` / RoboJuDo config `g1_asap_loco`

Policy B dynamic-NPC hand-match command:

```bash
.venv/bin/asimovbm-local \
  --robot g1 \
  --iterations 1 \
  --visible \
  --trace-backend real \
  --policy g1_robojudo_asap \
  --episode g1_point_to_point_dynamic_npcs \
  --viewer-speed 1.0 \
  --camera-view bystander \
  --episode-steps 900 \
  --start-delay 0 \
  --start-x-offset 0.35 \
  --run-id hand-validated-g1-policy-b-ep3
```

Omit `--episode` to run all filmed G1 episodes:

- `g1_point_to_point_open`
- `g1_point_to_point_static_obstacles`
- `g1_point_to_point_dynamic_npcs`

`--episode-steps` is the run timer override. The reference backend uses about
`0.08` simulated seconds per step; the real RoboJuDo path uses the MuJoCo
pipeline `dt`, usually about `0.02`, so `900` steps is about `18` simulated
seconds in real mode. Omit the flag to use each episode JSON's checked-in
`steps` value. Use `--viewer-speed 1.0` for realtime visual review, or a larger
value when you want the viewer to advance faster. Use
`--camera-view config`, `--camera-view arrival`, or `--camera-view bystander`
to choose the viewer POV from the episode JSON.

`--start-delay` overrides the controller hold time before navigation commands
are sent. Policy B's dynamic NPC episode defaults to `0` in `asimovbm-local` so
the ASAP run starts walking immediately like the survey recording. That same
policy-B dynamic NPC run also uses a `+0.35 m` start offset on the x-axis, which
moves the robot slightly forward toward the goal in ep3. Tune it with
`--start-x-offset`; use `--route-y-offset` only if the bystander view still
needs a side-lane tweak.

To watch just one episode in the MuJoCo viewer without writing benchmark
metrics:

```bash
cd g1_slam
../.venv/bin/python -m g1_slam \
  --config config/episodes/g1_point_to_point_open.json \
  --locomotion robojudo \
  --render \
  --camera-view arrival \
  --start-delay 0 \
  --steps 900 \
  --realtime-factor 1.0
```

Launch the metric dashboard after a validation run:

```bash
.venv/bin/python -m asimovbm.web.server \
  --artifact-root artifacts/local-validation \
  --survey-root artifacts/survey \
  --video-root artifacts/survey/videos \
  --survey-json-root artifacts/survey/json \
  --study-id pilot \
  --host 127.0.0.1 \
  --port 8765
```

Open `http://127.0.0.1:8765`, select the relevant `hand-validated-g1-*` run in
the `Runs` view, and compare metrics against the manually validated videos.

## Current Priorities

The remaining high-priority work is:

1. Improve the videos.
   - They should be sharper, smoother, and less blurry.
   - The first-person/arrival and bystander perspectives must show what the
     survey labels promise.
   - Each episode name should match what appears in the video.

2. Find and verify the episodes Luis pushed.
   - They may be on another branch, unpushed, or missing from this checkout.
   - This matters because those episodes are expected to be the correct
     simulation ground truth.

3. Make the website more intuitive.
   - Researcher views should group episode, video, prediction, survey result,
     and error clearly.
   - Survey participants should not need to understand the file structure.
   - Researchers should be able to click an episode and immediately understand
     what they are viewing.

4. Add a website button to launch simulation.
   - The button should run the command that generates benchmark data, MP4s, and
     JSON sidecars.
   - After the run, the website should refresh and show the new survey files.
   - Researchers should not need to copy terminal commands for common runs.

5. Add a website button to delete generated data.
   - It should clean survey/artifact folders in a controlled way.
   - It must clearly state whether it deletes videos, JSON sidecars, survey
     responses, or everything.
   - It should require confirmation before deleting.

The most urgent items are better videos, correct perspectives, and locating
Luis's episodes. Without those, the website works technically, but the survey
can still show wrong or low-quality evidence.

## Unity Cleanup History

Unity code was removed from this repo so the active codebase stays focused on
MuJoCo, metrics, website, video generation, and JSON artifacts.

Removed:

- `unity_mujoco_slam/`: Unity 2022.3 project.
- `tools/unity/`: Python preparer and C# templates.
- `unity-bootstrap.log`.
- `src/asimovbm/local_runner/unity_runner.py`.
- `src/asimovbm/local_runner/unity_ingest.py`.
- Unity tests under `tests/test_unity_mujoco_project.py`,
  `tests/local_runner/test_unity_ingest.py`, and `tests/tools/`.
- Unity docs and plans, including `docs/run-mujoco-unity.md` and old Unity
  planning docs under `docs/plans/` and `docs/brainstorms/`.

Kept and cleaned:

- `pyproject.toml`: removed `asimovbm-unity`; kept `asimovbm-local` and
  `asimovbm-web`.
- `.gitignore`: removed Unity-specific rules.
- `README.md` and `src/asimovbm/README.md`: removed old Unity sections.
- `final-rush-choices.md`: removed the Unity add-on block.
- `src/asimovbm/survey/prediction.py`: removed the `asimovbm.unity_trace.v1`
  prediction branch and related lazy imports.

Recovery points if Unity work is needed again:

- Safety branch: `paper-sub-backup` locally and on origin.
- Original Unity branches: `feat/unity-cinematic-capture` and
  `feat/robojudo-unity-video-generation`.
- Cleanup commits: `905e52e` and `fce8490`, merged into `paper-sub`.

At the time of cleanup, the repo was reduced by about 1100 files and 2.5
million lines, and the active test suite passed.

## Tests

Run all tests:

```bash
.venv/bin/python -m pytest
```

The active tests cover the local runner, metric library, reports, package
imports, webserver, survey design/storage/export/analysis, and `g1_slam`
pure-Python imports.

## Repository Layout

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
artifacts/local-validation/   # Local benchmark outputs.
artifacts/survey/             # Survey videos, sidecars, and responses.
```

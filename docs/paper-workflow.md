# Paper workflow

This repository contains the code and curated evidence for the ICRA 2026
AsimovBM paper. The canonical publication is
[`paper/AsimovBM_ICRA2026.pdf`](../paper/AsimovBM_ICRA2026.pdf); the focused
reproduction instructions are in [`paper/README.md`](../paper/README.md).

## Evidence flow

```text
g1_slam episode configs
        |
        v
asimovbm local runner -----> artifacts/local-validation/ (12 curated traces)
        |                                      |
        v                                      v
asimovbm/metrics/                    paper/analysis/paper_results.ipynb
                                                   ^
                                                   |
paper/data/human-survey/responses.csv -------------+
                                                   |
                                                   v
                                       paper/results/ + paper/assets/
```

The repository identity is “paper plus reproducible benchmark.” Generated
build debris, alternate poster material, stale paper drafts, and exploratory
plots are intentionally excluded.

## Canonical paper material

- Final manuscript: `paper/AsimovBM_ICRA2026.pdf`
- Published figures: `paper/assets/`
- Final anonymous survey cohort: `paper/data/human-survey/responses.csv`
- Published result tables: `paper/results/`
- Analysis entry points: `paper/analysis/`
- Objective validation traces: `artifacts/local-validation/`

The survey CSV contains 120 responses and the 17 fields used by the paper:
one robot-familiarity field and 16 Likert ratings. Google Forms timestamps were
removed because they are not part of the analysis.

## Objective metrics

Metric implementations live under `asimovbm/metrics/`, with the human-facing
editing guide in `metrics/README.md` and the formulas in
`docs/specs/social-navigation-metrics.md`. Metric behavior is covered by
`tests/metrics/`.

The weight-matrix figure is generated directly from the implemented registry:

```bash
.venv/bin/python paper/analysis/generate_metric_weight_matrix.py
```

## Simulation evidence

The 12 paper runs comprise four policy/viewpoint blocks (`q1`–`q4`), each
containing three navigation scenarios. There are two policies and two viewpoints.
Keep each run's manifest, report, episode metrics, metric JSON, and trace together; the traces
are the raw objective evidence behind the reported axis and feature scores.

Regenerate the metric dashboard:

```bash
.venv/bin/python tools/plot_local_validation_metrics.py \
  --root artifacts/local-validation \
  --output artifacts/local-validation/metric-visualizations
```

### Portable reference smoke check

This checks the navigation/metric pipeline with the portable 2D reference
backend. It does not execute the learned RoboJuDo policies used in the paper:

```bash
.venv/bin/asimovbm-local \
  --robot g1 \
  --iterations 1 \
  --trace-backend reference \
  --headless \
  --artifact-root artifacts/new-validation \
  --run-id reference-smoke
```

Policy A is `g1_robojudo_unitree`; Policy B is `g1_robojudo_asap`. Survey
blocks map as follows:

| Survey block | Policy | Viewpoint |
|---|---|---|
| Q1 | A | First person |
| Q2 | B | First person |
| Q3 | A | Third person |
| Q4 | B | Third person |

### Fresh real-policy runs

The released manifests record `trace_backend: real`, execution backend
`g1_robojudo_mujoco_trace_v1`, and `trace_source: robojudo_loop`.
To attempt new runs with that backend, use Python 3.11 or newer, initialize the
pinned submodules (including nested dependencies), and install the optional
simulation dependencies and upstream RoboJuDo package from the repository root:

```bash
python3 -m venv .venv
git submodule update --init --recursive
.venv/bin/python -m pip install -e '.[g1-mujoco]'
.venv/bin/python -m pip install -e g1_slam/third_party/RoboJuDo imageio
```

Install RoboJuDo's optional viewer module using its bundled installer and the
same environment (the upstream checkout manages this dependency separately):

```bash
source .venv/bin/activate
cd g1_slam/third_party/RoboJuDo
python submodule_install.py mujoco_viewer
cd ../../..
```

The pinned RoboJuDo checkout provides these model files under its `assets/`:

- Policy A (`g1`): `models/g1/unitree/policy_lstm_1.pt`.
- Policy B (`g1_asap_loco`):
  `models/g1/asap/dec_loco/20250109_231507-noDR_rand_history_loco_stand_height_noise-decoupled_locomotion-g1_29dof/model_6600.onnx`.

Check that these are actual model bytes after checkout, including Git LFS data
where needed. The generic `policies/g1/policy.onnx` catalog field is not the
weight source for this backend: it constructs the selected RoboJuDo config.
The `unitree_mujoco` submodule provides official Unitree assets for other
MuJoCo paths. Real runs require working MuJoCo graphics/viewer support;
headless execution does not remove the upstream dependency requirements. See
[upstream setup](../g1_slam/third_party/RoboJuDo/README.md) for platform-specific
dependencies and optional CPU-only PyTorch installation.

For example, run Policy A across all three G1 episodes in arrival view and save
fresh evidence separately from the released traces:

```bash
.venv/bin/asimovbm-local \
  --robot g1 \
  --policy g1_robojudo_unitree \
  --trace-backend real \
  --camera-view arrival \
  --iterations 1 \
  --headless \
  --artifact-root artifacts/new-validation \
  --run-id policyA-arrival
```

Repeat with `--policy g1_robojudo_asap` for B and `--camera-view bystander`
for the other viewpoint, using distinct run IDs. Select a single scenario with
`--episode g1_point_to_point_open`,
`--episode g1_point_to_point_static_obstacles`, or
`--episode g1_point_to_point_dynamic_npcs`. For the archived settings, run
Policy B's moving-NPC episode separately: its traces record a **0.35 m forward
start offset** and **zero start delay**, unlike the other ten runs (zero offset
and a 1 s delay). Use these additional flags for both Policy-B viewpoints:

```bash
--episode g1_point_to_point_dynamic_npcs --start-x-offset 0.35 --start-delay 0
```

Run Policy B's open and static episodes separately without those overrides.
The moving-NPC horizon is 1500 steps (30 s at 0.02 s); open and static configs
use 1400 steps. All runs use one iteration and zero lateral route offset.
The legacy manifests' top-level override fields are null even for the two
modified runs; inspect effective episode settings and trace metadata rather
than inferring defaults from those nulls. Preserve fresh manifests and traces
to compare settings; these commands are rerun instructions, not a claim that
fresh trajectories have been verified identical.

The [twelve-command G1 sweep](simulations/run-point-to-point-episodes-and-policies.md#g1-point-to-point-episodes)
shows each direct simulator combination and opens a viewer with `--render`.
To export new survey-format video with the local runner, add `--survey-export`,
`--survey-policy-id policy_a` (or `policy_b`), `--survey-view arrival` (or
`bystander`), `--survey-root artifacts/new-survey`, and
`--survey-video-max-duration 0` to preserve full duration. Fresh exports must
be identified as new stimuli; they cannot establish original survey provenance.

### View archived trajectories

The [replay gallery](../artifacts/reconstructed-videos/index.html) offers twelve
episode clips and four policy/viewpoint compilations reconstructed from archived
full joint poses, obstacles and camera settings, without rerunning dynamics or
policies. See [rendering instructions](../paper/README.md#view-or-regenerate-episode-videos).
Six historical clips recovered from Git are available in the
[archived video gallery](../artifacts/historical-videos/index.html), with source
commit and hash records. Their mapping to the four original rated videos has
not been established. The six
[legacy survey sidecars](../artifacts/survey/README.md) do not establish their
provenance. See the [implementation notes](../paper/IMPLEMENTATION_NOTES.md)
for measurement and statistical limitations.

## Paper analyses

Install the optional analysis dependencies:

```bash
.venv/bin/python -m pip install -e '.[paper]'
```

`paper/analysis/paper_results.ipynb` combines human ratings and validation
traces. `paper/analysis/simulation_results.ipynb` inspects the trace provenance
and metric dashboard. Focused scripts reproduce Figures 2, 3, 4, and 6 plus
the viewpoint statistics; see `paper/README.md` for exact commands.

The compact CSVs in `paper/results/` are the publication-facing outputs. Do
not add every exploratory notebook export back to the repository.

## Verification

Run the paper artifact contract and active package suites:

```bash
.venv/bin/python -m pytest \
  tests/test_paper_assets.py \
  tests/test_package_imports.py \
  tests/metrics \
  tests/local_runner \
  tests/survey \
  tests/reports \
  tests/web
```

Run the simulator-specific suite when its optional dependencies and submodules
are available:

```bash
.venv/bin/python -m pytest g1_slam/tests/test_navigation.py
```

## Maintenance rules

- Keep the final PDF, published figures, final survey data, result tables, and
  12 curated validation traces together.
- Do not commit LaTeX auxiliaries, notebook checkpoints, alternate posters,
  exploratory plots, or local editor files.
- Do not change metric formulas, survey scoring, simulation behavior, or paper
  conclusions as part of repository housekeeping.
- If the manuscript changes, replace the canonical PDF and update the figure
  and result maps in the same change.

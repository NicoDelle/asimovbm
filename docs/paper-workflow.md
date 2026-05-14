# Paper Workflow

This is the canonical guide for using the repo for the paper. It keeps the
current workflow in one place: simulation evidence, objective metrics, human
survey data, notebooks, and paper-ready outputs.

## What To Open First

- Reviewer or collaborator: start with this file, then open
  `paper/notebooks/paper_results.ipynb`.
- Paper author: use the commands and asset map below to regenerate or inspect
  current evidence.
- Future agent: preserve the assets listed here unless the user explicitly says
  otherwise.

## Current Paper Assets

```text
paper/notebooks/survey_results.ipynb
paper/notebooks/simulation_results.ipynb
paper/notebooks/paper_results.ipynb
paper/data/human-survey/raw-responses.csv
paper/data/human-survey/analysis_outputs/
artifacts/local-validation/
artifacts/local-validation/metric-visualizations/
artifacts/survey/
```

The `paper/` directory is for paper-facing notebooks and human-survey data.
Source code stays in `src/asimovbm/` and `g1_slam/`.

## Workflow Overview

```text
g1_slam episode configs
        |
        v
asimovbm-local runner
        |
        v
artifacts/local-validation/
        |
        v
src/asimovbm/metrics/ objective scores
        |
        v
paper/notebooks/simulation_results.ipynb

human survey CSV
        |
        v
paper/notebooks/survey_results.ipynb
        |
        v
paper/notebooks/paper_results.ipynb
```

## Objective Metrics

Metric implementation lives here:

```text
src/asimovbm/metrics/
```

Metric tests live here:

```text
tests/metrics/
```

The metric formulas and weights are specified in:

```text
docs/specs/social-navigation-metrics.md
```

Do not move or rewrite metric formulas during repository cleanup. Navigation can
change; scientific semantics should not change without a separate plan.

## Simulation Evidence

Active episode configs live under:

```text
g1_slam/config/episodes/
```

The current paper-facing validation outputs live under:

```text
artifacts/local-validation/
```

The generated metric visualization page lives at:

```text
artifacts/local-validation/metric-visualizations/index.html
```

Run a simple local validation from the repository root:

```bash
.venv/bin/asimovbm-local \
  --robot g1 \
  --iterations 1 \
  --headless \
  --run-id local-check
```

Run a visible RoboJuDo validation when the local RoboJuDo/MuJoCo dependencies
are installed:

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
  --run-id hand-validated-g1-policy-a
```

Policy mapping for the survey videos:

- Policy A: `g1_robojudo_unitree` / RoboJuDo config `g1`
- Policy B: `g1_robojudo_asap` / RoboJuDo config `g1_asap_loco`

Survey blocks map to policy and point of view:

| Survey block | Policy | Point of view |
|---|---|---|
| Q1 | A | first person |
| Q2 | B | first person |
| Q3 | A | third person |
| Q4 | B | third person |

Each block represents a bundle of three episodes: open floor, static obstacles,
and moving people.

## Human Survey Data

The raw survey export is tracked here:

```text
paper/data/human-survey/raw-responses.csv
```

Analysis outputs are tracked here:

```text
paper/data/human-survey/analysis_outputs/
```

These files are curated paper evidence. Do not delete them as generated junk.

## Notebooks

Open notebooks from `paper/notebooks/`:

- `survey_results.ipynb`: imports and explores human survey data.
- `simulation_results.ipynb`: imports and explores logged simulation metrics.
- `paper_results.ipynb`: combines survey and simulation summaries to check
  whether the benchmark agrees with survey outcomes.

The notebooks can be run from the repository root or from `paper/notebooks/`.

## Web Dashboard

Start the local metrics dashboard and survey app from the repository root:

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

Then open:

```text
http://127.0.0.1:8765
```

Use `Runs` for objective validation artifacts and `Prediction vs Survey` for
survey/prediction comparisons.

## Old-To-New Location Map

```text
paper_results.ipynb
  -> paper/notebooks/paper_results.ipynb

survey_results.ipynb
  -> paper/notebooks/survey_results.ipynb

simulation_results.ipynb
  -> paper/notebooks/simulation_results.ipynb

survey_results/Human-Robot Interaction Evaluation (Responses) - Form Responses 1.csv
  -> paper/data/human-survey/raw-responses.csv

survey_results/analysis_outputs/
  -> paper/data/human-survey/analysis_outputs/
```

The old `archive/server_client_architecture/` tree, runtime logs, `runs/`
outputs, and generated package metadata were removed from the active branch.
They remain recoverable from `paper-sub-backup-2` if needed.

## Tests

Run the relevant cleanup guardrails:

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

Run the full active suite when the local environment has the optional simulation
dependencies available:

```bash
.venv/bin/python -m pytest
```

## Maintenance Rules

- Keep `src/asimovbm/metrics/` and `tests/metrics/` discoverable and stable.
- Keep curated paper data and outputs tracked in git.
- Keep `artifacts/local-validation/` as the local runner output/evidence root
  unless a separate cleanup proves a narrower move is safe.
- Do not change metric formulas, survey scoring semantics, simulation behavior,
  or scientific conclusions as part of navigation cleanup.

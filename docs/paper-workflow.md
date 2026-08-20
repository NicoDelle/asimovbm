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

The 12 paper runs are organized as four survey blocks (`q1`–`q4`), two
policies, two viewpoints, and three navigation scenarios. Keep each run's
manifest, report, episode metrics, metric JSON, and trace together; the traces
are the raw objective evidence behind the reported axis and feature scores.

Regenerate the metric dashboard:

```bash
.venv/bin/python tools/plot_local_validation_metrics.py \
  --root artifacts/local-validation \
  --output artifacts/local-validation/metric-visualizations
```

Run a fresh headless validation:

```bash
.venv/bin/asimovbm-local \
  --robot g1 \
  --iterations 1 \
  --headless \
  --run-id local-check
```

Policy A is `g1_robojudo_unitree`; Policy B is `g1_robojudo_asap`. Survey
blocks map as follows:

| Survey block | Policy | Viewpoint |
|---|---|---|
| Q1 | A | First person |
| Q2 | B | First person |
| Q3 | A | Third person |
| Q4 | B | Third person |

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

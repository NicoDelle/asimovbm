# AsimovBM

AsimovBM is a simulation-based benchmark for estimating four human-perception
scores from robot telemetry: Perceived Dexterity, Perceived Safety, Perceived
Social Awareness, and Impression.

Read the [ICRA 2026 paper](paper/AsimovBM_ICRA2026.pdf) or start with the
[reproduction guide](paper/README.md). The broader
[paper workflow guide](docs/paper-workflow.md) explains how the benchmark code,
validation traces, survey responses, and published results fit together.

## Repository Map

```text
paper/                         Final paper, figures, analyses, and results.
artifacts/local-validation/    Curated local benchmark outputs and visualizations.
artifacts/survey/              Survey media/JSON/session artifacts.
asimovbm/                      Active Python package: runner, metrics, survey, web.
asimovbm/metrics/              Editable objective HRI metric implementations.
metrics/                       Human-facing metric editing guide.
g1_slam/                       Active robot episode configs and simulation package.
docs/specs/                    Metric specification.
docs/solutions/                Searchable notes from solved repo problems.
tests/                         Python tests for active package behavior.
```

## Active Entry Points

- Paper analysis: `paper/analysis/paper_results.ipynb`
- Simulation metric exploration: `paper/analysis/simulation_results.ipynb`
- Published result tables: `paper/results/`
- Metric editing guide: `metrics/README.md`
- Objective metric code: `asimovbm/metrics/`
- Metric tests: `tests/metrics/`
- Solved-problem notes: `docs/solutions/`
- Local runner: `asimovbm/local_runner/`
- Web dashboard and survey app: `asimovbm/web/`

## Quick Setup

Run commands from the repository root.

```bash
.venv/bin/python -m pip install -e '.[dev,paper]'
```

Run the active tests:

```bash
.venv/bin/python -m pytest
```

Run the simulator-specific navigation tests when its optional dependencies and
submodules are available:

```bash
.venv/bin/python -m pytest g1_slam/tests/test_navigation.py
```

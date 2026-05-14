# ASIMOV Benchmark

Local-first benchmark and paper workspace for Human-Robot Interaction evaluation.

Start here:

- [Paper workflow guide](docs/paper-workflow.md)

That guide explains where the metrics, simulation evidence, human survey data,
notebooks, and paper-ready outputs live.

## Repository Map

```text
paper/                         Paper notebooks and human survey data.
artifacts/local-validation/    Curated local benchmark outputs and visualizations.
artifacts/survey/              Survey media/JSON/session artifacts.
asimovbm/                      Active Python package: runner, metrics, survey, web.
asimovbm/metrics/              Editable objective HRI metric implementations.
metrics/                       Human-facing metric editing guide.
g1_slam/                       Active robot episode configs and simulation package.
docs/specs/                    Metric specification.
tests/                         Python tests for active package behavior.
```

## Active Entry Points

- Paper analysis: `paper/notebooks/paper_results.ipynb`
- Human survey exploration: `paper/notebooks/survey_results.ipynb`
- Simulation metric exploration: `paper/notebooks/simulation_results.ipynb`
- Metric editing guide: `metrics/README.md`
- Objective metric code: `asimovbm/metrics/`
- Metric tests: `tests/metrics/`
- Local runner: `asimovbm/local_runner/`
- Web dashboard and survey app: `asimovbm/web/`

## Quick Setup

Run commands from the repository root.

```bash
.venv/bin/python -m pip install -e .[dev]
```

Run the active tests:

```bash
.venv/bin/python -m pytest
```

See [docs/paper-workflow.md](docs/paper-workflow.md) for the current paper
workflow and validation commands.

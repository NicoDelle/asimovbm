# asimovbm Package

Active source code for the ASIMOV benchmark.

For the paper workflow, asset map, and run commands, use:

- [docs/paper-workflow.md](../docs/paper-workflow.md)

Code map:

```text
asimovbm/local_runner/   Local validation runner and artifact handling.
asimovbm/metrics/        Objective HRI metric implementations.
asimovbm/reports/        CSV/report exports.
asimovbm/survey/         Survey design, storage, export, and analysis.
asimovbm/web/            Local dashboard and survey web app.
```

Metric formulas should stay in `asimovbm/metrics/` and are guarded by
`tests/metrics/`. For the human-facing metric editing guide, open
`../metrics/README.md`.

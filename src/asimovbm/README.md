# asimovbm Package

Active source code for the ASIMOV benchmark.

For the paper workflow, asset map, and run commands, use:

- [docs/paper-workflow.md](../../docs/paper-workflow.md)

Code map:

```text
src/asimovbm/local_runner/   Local validation runner and artifact handling.
src/asimovbm/metrics/        Objective HRI metric implementations.
src/asimovbm/reports/        CSV/report exports.
src/asimovbm/survey/         Survey design, storage, export, and analysis.
src/asimovbm/web/            Local dashboard and survey web app.
```

Metric formulas should stay in `src/asimovbm/metrics/` and are guarded by
`tests/metrics/`.

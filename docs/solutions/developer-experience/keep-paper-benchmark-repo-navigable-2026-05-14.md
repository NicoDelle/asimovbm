---
title: Keep The Paper Benchmark Repo Navigable
date: 2026-05-14
last_updated: 2026-08-20
category: developer-experience
module: repository-structure
problem_type: developer_experience
component: development_workflow
severity: medium
applies_when:
  - "Cleaning a research benchmark repo that mixes notebooks, simulation code, metric code, generated evidence, and obsolete plans"
  - "Moving files to make paper analysis easier to find without changing scientific metric semantics"
  - "Deleting files that look unused but may still be referenced by notebooks, docs, tests, or generated dashboards"
  - "Consolidating a repo README into a short start-here map while moving detailed workflow guidance into a canonical doc"
  - "Splitting paper notebooks by evidence domain without changing metric, survey, or simulation behavior"
tags: [repo-cleanup, paper-workflow, metrics, notebooks, verification, readme, documentation-consolidation, evidence-preservation]
---

# Keep The Paper Benchmark Repo Navigable

## Context

The repo had become hard to navigate while the paper workflow was still moving quickly. Human survey notebooks, simulation outputs, metric code, web/survey tooling, historical plans, Unity leftovers, generated files, and examples all lived in different places. That made the benchmark difficult to debug because the important scientific pieces were not obvious.

Recent session history shows this cleanup happened in stages. First, Unity-specific code and plans were removed while preserving the MuJoCo/RoboJuDo benchmark core and a backup branch (session history). Later, the paper workflow was reorganized so notebooks and human survey data moved under `paper/`, metric code moved out of the `src/` indirection into `asimovbm/metrics/`, and a human-facing metric guide was added at `metrics/README.md` (session history). The final pass removed only files that were verified as unused: empty tracked placeholders, a typo survey artifact, an empty generated warning file, and stale examples.

The notebook workflow also became explicit: `survey_results.ipynb` is for human ratings, `simulation_results.ipynb` is for objective metric logs, and `paper_results.ipynb` is for the mixed survey x simulation agreement check. The root `README.md` is intentionally short; `docs/paper-workflow.md` is the canonical operational map. This avoided turning the README into a second long workflow document while still making the active entry points obvious.

What did not work was treating cleanup as simple deletion. Earlier notebook edits also overreached by adding analysis before the user wanted it, and opaque conversion code made reruns harder to reason about (session history). The durable fix was to separate roles first, then delete only after references and scientific evidence paths were checked.

## Guidance

Use an evidence-preserving cleanup sequence instead of deleting by intuition.

1. Create or refresh a backup branch before large cleanup. For this project, `paper-sub-backup-2` preserves the pre-cleanup state.
2. Decide the active repo identity first. For this project, the active identity is “paper plus reproducible benchmark,” not a frozen paper-only data dump and not a general robotics toolkit.
3. Use a two-level documentation shape:
   - `README.md` stays short: project identity, start-here pointer, repo map, active entry points, setup, and tests.
   - `docs/paper-workflow.md` carries detail: asset map, evidence pipeline, commands, notebook roles, old-to-new paths, and maintenance rules.
4. Make the core paths obvious:
   - `paper/analysis/` for the active notebooks and paper-figure scripts.
   - `paper/data/human-survey/responses.csv` for the final de-identified survey cohort.
   - `paper/results/` for compact publication-facing CSV evidence.
   - `paper/assets/` for the published figures only.
   - `artifacts/local-validation/` for curated objective validation evidence.
   - `asimovbm/metrics/` for editable metric implementations.
   - `metrics/README.md` for the metric editing guide.
   - `docs/paper-workflow.md` for the canonical workflow map.
5. Keep notebooks separated by evidence domain:
   - `paper/analysis/simulation_results.ipynb` for logged simulation metrics.
   - `paper/analysis/paper_results.ipynb` for the mixed survey/simulation validation check.
   - focused scripts beside them for the final paper figures and appendix statistics.
6. Preserve scientific semantics during navigation cleanup. Do not change metric formulas, survey scoring, simulation behavior, or paper conclusions as part of moving folders.
7. Before deleting a path, verify it with both exact path searches and broader symbol/name searches. For example, the unused cleanup pass checked candidate paths such as `examples/`, `artifacts/survey/pilo/participants.jsonl`, `.codex`, `g1_slam/.codex`, `g1_slam/assets/g1_nav.xml`, and `artifacts/local-validation/metric-visualizations/data_warnings.txt` before deletion.
8. After structural moves, run import and test gates that cover both the paper package and the simulator package.

The key pattern is: make the benchmark easier to read without narrowing the repo so much that results can no longer be regenerated.

## Why This Matters

Research repos accumulate useful evidence and stale scaffolding at the same time. Treating all generated-looking files as disposable is risky because some generated CSV/JSON/SVG artifacts are curated paper evidence. Treating every old plan, example, or placeholder as sacred is also risky because it hides the files that actually matter.

The workable middle ground is to classify files by role:

- Curated evidence stays tracked, especially the final paper, de-identified survey CSV, compact result tables, paper analyses, and selected local-validation artifacts.
- Active code stays close to its purpose, with metrics easy to locate and edit.
- Historical plans, stale examples, typo data, empty placeholders, and dead compatibility files should be removed or moved out once verified unused.
- A single guide, `docs/paper-workflow.md`, should explain the current map so future agents do not have to reverse-engineer the repo.

This reduces future debugging time because an agent can start from the paper workflow guide, inspect `metrics/README.md`, and then run the documented tests instead of scanning unrelated branches of old project history.

## When to Apply

- The user says the repo is confusing, too large, or hard to debug.
- Metrics or paper assets are hidden behind legacy package layout or stale folder names.
- Cleanup would touch generated-looking artifacts that may actually be curated evidence.
- A folder appears unused but is not obviously safe to delete.
- Large refactors are happening close to a paper or deadline and need a reversible checkpoint.

## Examples

Before deleting files that look unused:

```bash
rg -n "candidate/path|candidate_name|old_import_name" README.md docs paper asimovbm g1_slam tests tools pyproject.toml
git ls-files -z | xargs -0 -I{} sh -c '[ ! -s "$1" ] && printf "%s\n" "$1"' sh {}
```

Before accepting a remote cleanup or conflict-resolution commit, verify that the branch fast-forwarded cleanly and that the active notebook paths still exist:

```bash
git status --short --branch
git pull --ff-only origin paper-sub
git reflog --date=iso -8
rg --files paper/analysis paper/results docs/solutions | sort
```

Notebook path sanity check:

```bash
jq -r '.cells[] | select(.cell_type=="code") | .source | join("")' paper/analysis/*.ipynb \
  | rg -n "paper/data|artifacts/local-validation|read_csv|rglob"
```

For this cleanup, a file was only removed after it had no active references or was confirmed generated/empty:

```text
.codex
g1_slam/.codex
g1_slam/assets/g1_nav.xml
artifacts/survey/pilo/participants.jsonl
artifacts/local-validation/metric-visualizations/data_warnings.txt
examples/
```

After structural cleanup, run both suites because `asimovbm` and `g1_slam` are separate package surfaces:

```bash
.venv/bin/python -m pytest
.venv/bin/python -m pytest g1_slam/tests/test_navigation.py
```

## Related

- `README.md`
- `docs/paper-workflow.md`
- `metrics/README.md`
- `docs/specs/social-navigation-metrics.md`
- `paper-sub-backup-2` preserves the pre-cleanup state for recovery.

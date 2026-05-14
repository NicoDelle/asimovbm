---
title: "refactor: Simplify paper workflow repo layout"
type: refactor
status: completed
date: 2026-05-14
origin: docs/brainstorms/2026-05-14-paper-workflow-repo-cleanup-requirements.md
---

# refactor: Simplify paper workflow repo layout

## Summary

Reorganize the repository around the paper workflow without changing scientific behavior. The implementation should preserve the active notebooks, survey data, curated paper evidence, and metric code, then make them easy to find through one canonical guide and a smaller set of obvious folders.

---

## Problem Frame

The repo currently exposes its history more than its current workflow. Active metric code, simulation code, survey data, notebooks, generated evidence, old architecture experiments, logs, and runtime outputs are spread across unrelated folders, which makes the benchmark hard to debug and the paper results hard to inspect.

---

## Assumptions

This plan follows the user's latest direction to decide implementation details pragmatically, keep the metrics and paper files, and avoid overcomplicating the cleanup.

- The implementation can introduce a small `paper/` directory for paper-facing notebooks and human-survey assets, while leaving active Python packages in their current package locations.
- `docs/paper-workflow.md` is the canonical usage guide because repo `.gitignore` already permits markdown under `docs/` and the user asked for one tidy markdown file.
- `artifacts/` remains the canonical local-runner output/evidence location unless implementation proves a specific subset can move with low risk. This avoids breaking existing runner and web paths during cleanup.
- Current notebook naming must be reconciled during implementation. The working tree may contain both `paper_results.ipynb` and `survey_results.ipynb`; preserve active content first, then document one canonical human-survey notebook role.

---

## Requirements

- R1. Make the paper workflow obvious: simulation evidence, objective metrics, human survey data, analysis notebooks, and paper-ready outputs must be connected and findable.
- R2. Preserve `paper_results.ipynb` or its intentional renamed successor as the active human-survey analysis notebook.
- R3. Preserve active paper-facing notebooks and outputs, including `simulation_results.ipynb` and `survey_results/analysis_outputs/` when present.
- R4. Keep the human survey CSV and curated analysis outputs tracked in git unless a later explicit decision changes that.
- R5. Make objective metric code and documentation easy to discover from the paper workflow.
- R6. Keep existing metric implementations and metric tests intact. Do not rewrite formulas or move metric code as a side effect.
- R7. Treat curated paper evidence as paper-supporting assets, not junk.
- R8. Produce one canonical, tidy markdown usage guide.
- R9. Make existing README or scattered documentation point to the canonical guide instead of duplicating stale instructions.
- R10. Cover local validation, metric computation, survey evidence, human survey data, notebook analysis, and paper-ready results in the guide.
- R11. Include entry points for collaborators, paper authors, and future agents.
- R12. If paper-facing files move, include an old-to-new location map.
- R13. Before cleanup, record `git status --short`, enumerate modified/untracked paper assets, and confirm backup coverage.
- R14. Verify `paper-sub-backup-2` exists, but do not treat it as sufficient protection for dirty working-tree assets.
- R15. Classify old experiments, logs, caches, generated package metadata, and non-curated runtime outputs as cleanup candidates.
- R16. Keep, move, or document curated paper evidence intentionally.
- R17. Move files physically only when it materially improves navigation or debuggability.
- R18. Do not create new workflow automation, new scientific outputs, or new academic validation machinery.
- R19. Do not change metric formulas, survey scoring semantics, simulation behavior, or scientific conclusions.
- R20. Run the relevant test suite after reorganization.
- R21. Update imports, scripts, docs, and notebook paths if files move.
- R22. Include lightweight paper sanity checks, especially survey CSV row count and notebook input paths.
- R23. The final repo should answer "where are the metrics, human data, paper notebook, and curated evidence?" without a repo-wide search.

**Origin actors:** A1 paper author, A2 reviewer/collaborator, A3 future coding agent.
**Origin flows:** F1 paper workflow navigation, F2 cleanup execution.
**Origin acceptance examples:** AE1 through AE5 from the origin requirements document.

---

## Scope Boundaries

- Do not delete active paper notebooks, survey CSVs, or curated analysis outputs.
- Do not delete, rewrite, or relocate active metric implementations as part of this cleanup.
- Do not change metric formulas, survey scoring, simulation behavior, or scientific conclusions.
- Do not turn this into a full rewrite of `g1_slam`, `local_runner`, or the web dashboard.
- Do not add a new data platform, external storage workflow, or heavy reproducibility framework in this step.
- Do not solve the deeper academic validation questions now. This cleanup is for navigation, debuggability, and preservation.

### Deferred to Follow-Up Work

- Academic validation improvements: separate plan after the benchmark is simpler to debug.
- Larger benchmark behavior fixes: separate debugging work after the active workflow is easier to run and inspect.
- Moving `artifacts/` wholesale: defer unless implementation proves runner, web, docs, and tests can support it without path churn.

---

## Context & Research

### Relevant Code and Patterns

- `src/asimovbm/metrics/` contains the objective metric implementations, registry, scoring, weights, and models. Keep this package location stable.
- `tests/metrics/` contains the metric test suite that should remain the main guardrail for unchanged formulas.
- `src/asimovbm/local_runner/` owns local validation artifact handling and CSV/report generation.
- `tests/local_runner/` covers artifact manifests, catalog behavior, CLI modes, metric extraction, and trace building.
- `src/asimovbm/survey/` and `tests/survey/` cover survey analysis, comparison, export, storage, prediction, and video manifest behavior.
- `src/asimovbm/web/` and `tests/web/` cover the existing dashboard and artifact index routes.
- `g1_slam/` contains active robot/simulation code and tests. Treat it as active unless a specific file is runtime clutter.
- `survey_results/Human-Robot Interaction Evaluation (Responses) - Form Responses 1.csv` is the human-survey raw data currently named by the workflow.
- `survey_results/analysis_outputs/` contains paper-facing analysis output CSVs that should be preserved.
- Current docs are spread across `README.md`, `src/asimovbm/README.md`, `docs/run-web-metrics-survey.md`, `docs/run-server.md`, `docs/simulations/`, `docs/specs/social-navigation-metrics.md`, and `docs/metrics_research/`.

### Institutional Learnings

- No `docs/solutions/` directory was present during planning, so there are no prior solution notes to carry forward.

### External References

- None. This is a repo-local cleanup and should rely on current code/tests, not external guidance.

---

## Key Technical Decisions

- Use `docs/paper-workflow.md` as the single canonical guide. This avoids a second tracked markdown location and fits the repo's current `.gitignore` rules.
- Keep package code in place. Navigation should improve through the guide and folder cleanup before moving active Python modules.
- Create a small `paper/` asset area for paper-facing notebooks and human survey data if implementation confirms paths can be updated cleanly.
- Keep curated evidence in git. Generated files are only cleanup candidates when they have no documented paper role.
- Delete obvious runtime clutter and generated metadata after backup verification, not before.
- Prefer deletion of obsolete archived experiments over moving them into another archive layer, relying on the backup branch for recovery.

---

## Open Questions

### Resolved During Planning

- Canonical guide path: use `docs/paper-workflow.md`.
- Paper-facing asset area: use `paper/` for notebooks and human-survey assets where moves improve clarity.
- Metric code location: keep `src/asimovbm/metrics/` unchanged and document it clearly.
- Runtime/evidence artifacts: keep `artifacts/` as-is for now, classify contents in the guide, and avoid wholesale moves.
- Cleanup posture: delete obvious clutter only after backup and reference checks.

### Deferred to Implementation

- Active human-survey notebook name: decide whether `paper_results.ipynb`, `survey_results.ipynb`, or both are intentional. Preserve content first; avoid duplicate canonical notebooks.
- Exact artifact classification: inspect each candidate before delete/move. Anything named by the guide as paper evidence stays.
- Test environment gaps: if a full suite cannot run because of missing local dependencies, document the missing dependency and run all available relevant tests instead of claiming success.

---

## Output Structure

    docs/
      paper-workflow.md
      plans/
        2026-05-14-002-refactor-paper-workflow-repo-cleanup-plan.md
    paper/
      notebooks/
        paper_results.ipynb or survey_results.ipynb
        simulation_results.ipynb
      data/
        human-survey/
          raw-responses.csv
          analysis_outputs/
            *.csv

`paper/` should contain paper-facing assets, not source code. Source code remains under `src/asimovbm/` and `g1_slam/`.

---

## Implementation Units

### U1. Inventory and Safety Gate

**Goal:** Establish the exact current state before moving or deleting anything.

**Requirements:** R13, R14, R16

**Dependencies:** None

**Files:**
- Read: `paper_results.ipynb`
- Read: `survey_results.ipynb`
- Read: `simulation_results.ipynb`
- Read: `survey_results/`
- Read: `artifacts/`
- Read: `archive/`
- Read: `logs/`
- Read: `runs/`

**Approach:**
- Record the dirty working tree state and explicitly identify modified/untracked paper assets.
- Verify the committed backup branch exists.
- Verify dirty notebook/data assets are backed up separately or still intentionally present.
- Build a classification list: active code, curated paper evidence, paper notebooks/data, docs, examples, archive candidates, generated runtime clutter.

**Execution note:** Characterization-first. No file move or deletion should happen until this inventory is complete.

**Patterns to follow:**
- Origin requirements R13 and R14.
- Existing git backup branch `paper-sub-backup-2`.

**Test scenarios:**
- Happy path: active notebooks and survey outputs are listed before any cleanup begins.
- Edge case: both `paper_results.ipynb` and `survey_results.ipynb` exist; implementation records their roles before choosing a canonical destination.
- Error path: backup branch or dirty asset backup is missing; implementation stops before destructive cleanup.

**Verification:**
- A written inventory is reflected in `docs/paper-workflow.md` or implementation notes.
- No paper asset has been deleted before classification.

---

### U2. Canonical Paper Workflow Guide

**Goal:** Create one guide that explains the repository through the paper workflow rather than through implementation history.

**Requirements:** R1, R5, R8, R9, R10, R11, R12, R23

**Dependencies:** U1

**Files:**
- Create: `docs/paper-workflow.md`
- Modify: `README.md`
- Modify: `src/asimovbm/README.md`
- Modify: `docs/run-web-metrics-survey.md`
- Modify: `docs/run-server.md`
- Modify: `docs/simulations/run-local-validation.md`
- Modify: `docs/simulations/run-point-to-point-episodes-and-policies.md`
- Modify: `docs/specs/social-navigation-metrics.md`

**Approach:**
- Make `docs/paper-workflow.md` the single entry point for paper usage.
- Keep supporting docs only where they add scoped detail; otherwise point them back to the guide.
- Include sections for collaborator inspection, paper-author reproduction, and future-agent maintenance.
- Include an old-to-new map for any file moved during U3 or U4.

**Patterns to follow:**
- Existing docs under `docs/simulations/` for command-level detail.
- Existing metric spec in `docs/specs/social-navigation-metrics.md`.

**Test scenarios:**
- Happy path: a fresh reader can locate metrics, simulation evidence, human survey data, notebooks, and paper outputs from the guide.
- Edge case: supporting docs still make sense when opened directly because they point back to the canonical guide.
- Integration: every path named in the guide exists after reorganization.

**Verification:**
- There is exactly one canonical paper workflow guide.
- `README.md` points to that guide instead of duplicating the full workflow.

---

### U3. Paper Notebooks and Human Survey Assets

**Goal:** Move or document paper-facing notebooks and human survey assets so they are easy to find and still runnable.

**Requirements:** R2, R3, R4, R10, R12, R16, R17, R21, R22

**Dependencies:** U1, U2

**Files:**
- Move or preserve in place: `paper_results.ipynb`
- Move or preserve in place: `survey_results.ipynb`
- Move or preserve in place: `simulation_results.ipynb`
- Move or preserve in place: `survey_results/Human-Robot Interaction Evaluation (Responses) - Form Responses 1.csv`
- Move or preserve in place: `survey_results/analysis_outputs/*.csv`
- Create as needed: `paper/notebooks/`
- Create as needed: `paper/data/human-survey/`
- Create as needed: `paper/data/human-survey/analysis_outputs/`
- Modify: `docs/paper-workflow.md`
- Create: `tests/test_paper_assets.py`

**Approach:**
- Prefer a clear `paper/notebooks/` and `paper/data/human-survey/` layout if notebook paths can be updated cleanly.
- Rename only where it reduces confusion, such as replacing the long survey CSV filename with a documented `raw-responses.csv`.
- If moving a file creates more risk than clarity, keep it in place and document it in the guide instead.
- Update notebook path references after any move.

**Execution note:** Preserve-first. Copy/move decisions should happen after checking notebook contents and current dirty state.

**Patterns to follow:**
- Notebook cells should keep the user's readable style: simple pandas exploration and explicit, commented conversion logic.
- Keep paper data in git as required by the origin document.

**Test scenarios:**
- Happy path: paper asset sanity test finds the raw survey CSV, analysis output CSVs, and canonical notebooks at documented paths.
- Happy path: raw survey CSV loads and has at least one response row.
- Edge case: if both human-survey notebooks exist, only one canonical role is documented while the other is either preserved as distinct or removed only after content comparison.
- Error path: a notebook references a stale input path; the paper asset test fails before the cleanup is considered complete.

**Verification:**
- The active human-survey notebook and simulation notebook are still present.
- Human survey raw data and curated output CSVs remain tracked.
- Notebook inputs resolve from a fresh checkout.

---

### U4. Metrics Navigation Without Metric Refactor

**Goal:** Make metrics easy to discover while keeping implementation and tests stable.

**Requirements:** R5, R6, R10, R19, R20, R23

**Dependencies:** U2

**Files:**
- Modify: `docs/paper-workflow.md`
- Modify: `docs/specs/social-navigation-metrics.md`
- Preserve: `src/asimovbm/metrics/`
- Preserve: `tests/metrics/`

**Approach:**
- Add a metrics map in the canonical guide that links the paper workflow to objective metric code, metric specs, metric tests, and generated reports.
- Do not move metric implementation files.
- Do not change scoring semantics, formulas, weights, or registry behavior during this cleanup.

**Patterns to follow:**
- Existing metric registry and test structure under `src/asimovbm/metrics/` and `tests/metrics/`.

**Test scenarios:**
- Happy path: all existing metric tests still pass after documentation/path cleanup.
- Edge case: documentation names the code location and the spec location without implying formulas changed.
- Integration: local runner metric extraction tests still pass if docs or paths around artifacts changed.

**Verification:**
- No metric implementation diff exists except documentation-only references.
- Metric test suite remains green.

---

### U5. Remove Obvious Clutter and Stale Experiments

**Goal:** Reduce repo noise without deleting active code or curated evidence.

**Requirements:** R7, R15, R16, R17, R18, R19

**Dependencies:** U1, U2

**Files:**
- Modify: `.gitignore`
- Delete when confirmed unused: `logs/robojudo.log`
- Delete when confirmed unused: `g1_slam/logs/robojudo.log`
- Delete when confirmed unused: `g1_slam/MUJOCO_LOG.TXT`
- Delete when confirmed unused: `runs/map.pgm`
- Delete when confirmed unused: `runs/path.csv`
- Delete when confirmed unused: `g1_slam/src/g1_slam.egg-info/`
- Delete when confirmed unused: `g1_slam/.pytest_cache/`
- Delete when confirmed unused: `tests/__pycache__/`
- Delete or archive-by-deletion after reference check: `archive/server_client_architecture/`
- Modify: `docs/paper-workflow.md`

**Approach:**
- Delete generated logs, caches, package metadata, and runtime outputs after confirming they are not curated evidence.
- Update `.gitignore` so these files do not reappear as tracked clutter.
- For old architecture experiments, prefer deletion from the active branch after confirming no imports, tests, or paper docs reference them. Recovery remains available through the backup branch.
- Do not delete anything under `artifacts/` unless U1 classifies it as non-curated and no active path references it.

**Patterns to follow:**
- Current `.gitignore` already ignores `.venv/`, `__pycache__/`, `*.egg-info/`, `.pytest_cache/`, and local Compound Engineering config.

**Test scenarios:**
- Happy path: cleanup candidates disappear from active status and do not regenerate as tracked files after tests.
- Edge case: a candidate file is referenced by docs/tests; implementation keeps it or updates the reference intentionally.
- Error path: a file under `artifacts/` lacks obvious role; implementation classifies it before deletion rather than treating generated output as junk by default.

**Verification:**
- Active code, notebooks, survey assets, metric code, and curated evidence remain.
- Runtime clutter and stale archive code no longer dominate navigation.

---

### U6. Final Validation and Fresh-Checkout Sanity

**Goal:** Prove the cleanup preserved behavior and made paper assets locatable.

**Requirements:** R20, R21, R22, R23

**Dependencies:** U3, U4, U5

**Files:**
- Test: `tests/test_paper_assets.py`
- Test: `tests/test_package_imports.py`
- Test: `tests/metrics/`
- Test: `tests/local_runner/`
- Test: `tests/survey/`
- Test: `tests/reports/`
- Test: `tests/web/`
- Test: `g1_slam/tests/test_navigation.py`

**Approach:**
- Run the relevant existing Python tests for touched areas.
- Run metric, local runner, survey, report, web, package import, and paper asset sanity checks.
- Run `g1_slam` tests when its local dependencies are available; if not, record the missing dependency plainly and keep the cleanup limited to path-safe changes.
- Confirm documented paths exist and notebook inputs resolve.

**Execution note:** Treat failures from path moves as cleanup blockers, not as future polish.

**Patterns to follow:**
- Existing pytest-based test layout.
- New paper asset sanity test should be lightweight and deterministic.

**Test scenarios:**
- Happy path: all available relevant tests pass.
- Happy path: paper asset sanity test validates survey CSV row count and notebook input paths.
- Edge case: environment lacks `g1_slam` runtime dependency; implementation documents the dependency failure and still runs all non-blocked tests.
- Integration: docs name only paths that exist after the cleanup.

**Verification:**
- Test results are recorded in the final implementation summary.
- A future contributor can navigate the repo through `README.md` and `docs/paper-workflow.md` without scanning unrelated folders.

---

## System-Wide Impact

- **Interaction graph:** Documentation, notebooks, survey data paths, artifact references, and test discovery are affected. Runtime package imports should not change.
- **Error propagation:** New path mistakes should surface through paper asset sanity tests, existing local runner tests, and notebook input checks.
- **State lifecycle risks:** Dirty notebooks and untracked output CSVs are the main risk. U1 prevents accidental loss before cleanup.
- **API surface parity:** Python package imports under `src/asimovbm/` should remain stable. No public API or CLI behavior should change unless only a doc path changes.
- **Integration coverage:** Existing metric/local-runner/survey/web tests plus `tests/test_paper_assets.py` cover the cleanup better than documentation review alone.
- **Unchanged invariants:** Metric formulas, metric weights, survey scoring semantics, simulation behavior, scientific conclusions, and benchmark methodology remain unchanged.

---

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Dirty notebook or survey-output work is lost during cleanup. | U1 inventories dirty assets and confirms backup coverage before any move/delete. |
| Moving paper files breaks notebooks. | U3 updates notebook paths and U6 validates notebook input paths. |
| The canonical guide becomes another stale doc. | U2 makes `README.md` point to the guide and avoids duplicating full workflow instructions elsewhere. |
| Deleting archived code removes useful history. | U5 deletes only after reference checks and relies on `paper-sub-backup-2` for recovery. |
| Moving `artifacts/` breaks runner or web assumptions. | Keep `artifacts/` in place for this cleanup unless a specific subset is proven safe to move. |
| Tests cannot all run locally because of simulation dependencies. | U6 records missing dependency failures plainly and runs every non-blocked relevant test. |

---

## Documentation / Operational Notes

- The final implementation summary should include the exact paper guide path, old-to-new file map, retained curated evidence locations, cleanup deletions, and test results.
- Avoid adding more README-style files unless they are short pointers to `docs/paper-workflow.md`.
- If implementation creates `paper/`, it should contain paper-facing assets only, not package source code.

---

## Sources & References

- **Origin document:** `docs/brainstorms/2026-05-14-paper-workflow-repo-cleanup-requirements.md`
- Existing metric code: `src/asimovbm/metrics/`
- Existing metric tests: `tests/metrics/`
- Existing local runner code: `src/asimovbm/local_runner/`
- Existing local runner tests: `tests/local_runner/`
- Existing survey code: `src/asimovbm/survey/`
- Existing survey tests: `tests/survey/`
- Existing web tests: `tests/web/`
- Existing simulation package: `g1_slam/`
- Existing simulation tests: `g1_slam/tests/test_navigation.py`

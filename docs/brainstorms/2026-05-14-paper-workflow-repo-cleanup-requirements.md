---
date: 2026-05-14
topic: paper-workflow-repo-cleanup
---

# Paper Workflow Repo Cleanup

## Summary

Reorganize the repository around the paper workflow so a reader can move from simulation evidence, to objective metrics, to human survey data, to analysis, to paper-ready outputs without hunting through unrelated folders. The immediate goal is simplification and debuggability: keep the active metrics and paper notebooks intact, reduce repo confusion, and produce one canonical usage guide before addressing heavier academic/reproducibility polish.

---

## Problem Frame

The repository has grown through several phases: black-box benchmark exploration, local validation, `g1_slam` integration, survey video generation, human survey collection, metric analysis, and paper-result notebook work. The current layout exposes that history directly. Active code, generated evidence, old architecture experiments, survey files, runtime logs, examples, and paper notes all sit near each other without a clear hierarchy.

This makes the project harder to navigate than it needs to be. Metrics are implemented in one area, simulation and policy code live elsewhere, generated paper evidence is spread through artifact folders, and the human survey analysis notebook is easy to miss. The benchmark is currently difficult to debug partly because the active path is hard to separate from old experiments and runtime clutter. For paper work, the top-level mental model should be the research pipeline, not the incidental order in which the repository evolved.

---

## Actors

- A1. Paper author: uses the repo to produce paper figures, tables, survey analysis, and evidence.
- A2. Reviewer or collaborator: opens the repo and needs to understand the paper workflow without prior context.
- A3. Future coding agent: needs a clear structure and single usage guide before making cleanup, analysis, or metric changes.

---

## Key Flows

- F1. Paper workflow navigation
  - **Trigger:** A collaborator opens the repository to understand how the paper results are produced.
  - **Actors:** A1, A2, A3
  - **Steps:** Start from the canonical usage guide, identify the paper workflow stages, locate curated simulation evidence, locate metric code, locate human survey data, open `paper_results.ipynb`, and understand which command or notebook produces each output.
  - **Outcome:** The collaborator can explain the repo’s paper pipeline without reverse-engineering folder history.
  - **Covered by:** R1, R2, R3, R4, R5, R6, R7, R8, R18

- F2. Cleanup execution
  - **Trigger:** A contributor starts the cleanup work after this requirements doc.
  - **Actors:** A1, A3
  - **Steps:** Confirm the backup branch exists, classify files as active code, curated evidence, documentation, examples, archived material, or generated junk, reorganize the repo around the paper workflow, update the canonical usage guide, and run tests.
  - **Outcome:** The repo is easier to navigate and current workflows still work.
  - **Covered by:** R9, R10, R11, R12, R13, R14, R15, R16, R17, R19, R20

---

## Requirements

**Paper workflow navigation**

- R1. The top-level repository structure must make the paper workflow obvious: simulation or robot behavior evidence, objective metrics, human survey data, analysis notebooks, and paper-ready outputs must be findable as connected stages.
- R2. The cleanup must keep `paper_results.ipynb` as the active human survey analysis notebook.
- R3. The cleanup must also preserve active paper-facing notebooks or outputs that exist in the working tree, including `simulation_results.ipynb` and `survey_results/analysis_outputs/` when present.
- R4. The human survey CSV and any curated analysis outputs needed for the paper must remain tracked in git unless a later explicit decision says otherwise.
- R5. Objective metric code and documentation must be easier to discover from the paper workflow, not hidden behind unrelated implementation history.
- R6. Existing metric implementations and metric tests must be kept intact during this cleanup; the cleanup may improve navigation to metrics but must not rewrite formulas or move metric code as a side effect.
- R7. Curated paper evidence means assets named by the canonical guide as supporting a paper input, notebook output, result table, figure, survey result, metric comparison, or reproducibility step. Generated files without that role are candidates for quarantine, deletion, or gitignore.

**Documentation**

- R8. The cleanup must produce one canonical, tidy markdown usage guide that explains the paper workflow end to end.
- R9. Existing README or scattered documentation may remain, but they should point toward the canonical guide instead of duplicating partial or stale instructions.
- R10. The canonical guide must cover how to locate existing assets and run existing supported commands or notebooks for the major paper stages: local validation, metric computation, survey evidence, human survey data, notebook analysis, and paper-ready results.
- R11. The canonical guide must include clear entry points for reviewer/collaborator inspection, paper-author reproduction, and future-agent maintenance.
- R12. If paper-facing files move, the canonical guide must include a concise old-to-new location map.

**Cleanup and preservation**

- R13. Before cleanup work starts, record `git status --short`, enumerate modified and untracked paper assets, and confirm they are backed up or intentionally preserved.
- R14. The cleanup must verify that `paper-sub-backup-2` exists, but that branch is not sufficient protection for dirty working-tree assets.
- R15. Old architecture experiments, logs, caches, generated package metadata, and non-curated runtime outputs are cleanup candidates.
- R16. Curated paper evidence is not junk by default; it should be kept, moved, or clearly documented rather than deleted casually.
- R17. Physical file moves should be used only when they materially improve navigation or debuggability; if a guide, index, or small asset map solves the confusion with less path churn, prefer that.
- R18. The cleanup documents and simplifies the existing workflow; it must not create new workflow automation, new scientific outputs, or new academic validation machinery.
- R19. The cleanup must not change metric formulas, survey scoring semantics, simulation behavior, or scientific conclusions.

**Validation**

- R20. After reorganization, the current test suite relevant to touched areas must pass.
- R21. If files move, imports, scripts, docs, and notebook paths must be updated so the repo works from a fresh checkout.
- R22. Validation must include lightweight paper sanity checks, such as confirming the survey CSV row count and confirming active notebooks still locate their inputs.
- R23. The cleanup is incomplete if a future contributor still has to search across unrelated folders to answer “where are the metrics, human data, paper notebook, and curated evidence?”

---

## Acceptance Examples

- AE1. **Covers R1, R5, R7, R23.** Given a fresh checkout, when a collaborator wants to understand the paper pipeline, they can start from the canonical guide and locate metric code, curated evidence, survey data, and `paper_results.ipynb` without scanning the whole tree.
- AE2. **Covers R2, R3, R4, R16.** Given the current human survey work, when cleanup is complete, `paper_results.ipynb`, `simulation_results.ipynb` when present, the human survey CSV, and curated analysis outputs are still present and intentionally documented as paper assets.
- AE3. **Covers R8, R9, R10.** Given multiple existing README-style instructions, when cleanup is complete, there is one canonical usage guide and other docs link to it while containing only clearly scoped supporting detail.
- AE4. **Covers R19, R20, R21, R22.** Given reorganized files, when the relevant tests and lightweight paper sanity checks are run, they pass without requiring undocumented manual path fixes.
- AE5. **Covers R17, R18.** Given a candidate file move, when a guide entry or asset map would solve the confusion with less risk, the cleanup keeps the file in place and documents it instead of moving it.

---

## Success Criteria

- A paper collaborator can understand the project structure in under a few minutes by reading one guide.
- The repo visibly follows the paper workflow rather than exposing old implementation history as the primary navigation model.
- The active notebooks, human survey data, curated metric/simulation evidence, and objective metric code are easy to locate.
- Cleanup removes or quarantines obvious clutter without losing paper evidence or changing scientific behavior.
- The benchmark is easier to debug because active files, old experiments, generated clutter, and paper evidence are clearly separated.
- A downstream planning or coding agent can execute the cleanup without inventing scope boundaries.

---

## Scope Boundaries

- Do not delete `paper_results.ipynb`.
- Do not delete active paper-facing files such as `simulation_results.ipynb` or curated `survey_results/analysis_outputs/` files without an explicit later decision.
- Do not delete, rewrite, or relocate active metric implementations as part of this cleanup.
- Do not remove curated paper evidence simply because it is generated.
- Do not change metric formulas, scoring weights, survey question semantics, or simulation behavior as part of this cleanup.
- Do not redesign the research methodology.
- Do not turn the cleanup into a full rewrite of `g1_slam` or the local runner.
- Do not require external storage or a new data platform for the current cleanup.
- Do not solve heavier academic validation issues in this step; first make the benchmark understandable and debuggable.

---

## Key Decisions

- Optimize for paper workflow navigation over pure package architecture.
- Keep curated paper evidence in git, accepting some repository weight for paper reproducibility and collaboration.
- Prioritize simplification and debuggability before academic polish.
- Reorganize files physically only where it improves clarity enough to justify path churn.
- Use one canonical usage guide as the source of truth for how to use the repo.
- Treat `paper-sub-backup-2` as the committed pre-cleanup recovery point, and separately preserve dirty paper assets before cleanup.

---

## Dependencies / Assumptions

- The branch `paper-sub-backup-2` exists and points to the current pre-cleanup state.
- The active Python package remains under normal package structure unless planning finds a low-risk reason to move it.
- The current paper workflow includes existing human survey data, not only future survey collection.
- Some tracked artifacts are intentionally retained because they support the paper.
- The working tree may contain ongoing notebook changes and untracked analysis outputs; cleanup planning and execution must avoid overwriting them.

---

## Outstanding Questions

### Resolve Before Planning

- None.

### Deferred to Planning

- [Affects R1-R5][Technical] Decide the exact target folder names for paper workflow stages.
- [Affects R7, R15-R17][Technical] Classify each current artifact/log/archive folder as keep, move, quarantine, or delete.
- [Affects R8-R12][Technical] Choose the canonical usage guide path and decide which existing docs should link to it.
- [Affects R20-R22][Technical] Define the exact test and lightweight paper sanity-check commands required after reorganization.

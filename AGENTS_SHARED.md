# AGENTS_SHARED.md

Shared instructions for agents working on **Paper HRI**. This file is intended
to be committed to git, so keep it free of local absolute paths, private URLs,
credentials, and machine-specific settings.

## Project Context

Paper HRI is a human-robot interaction benchmark project.

Current goals:

- Minimum: benchmark specifications.
- Target: benchmark MVP.
- Deadline: 15 May 2026.

Use this repository for executable work, benchmark artifacts, drafts, generated
outputs, and project files that should live on disk.

Before changing benchmark scope, metric definitions, documents, or
implementation direction, inspect the available project context. If a local
`AGENTS.md` exists, check it for private workspace links and local lookup
instructions before relying only on repository files.

During the final MVP rush, always inspect `final-rush-choices.md` before
changing episodic validation, scenario interfaces, observation boundaries,
metric computation, or aggregation behavior.

When replacing smoke episodic-validation scaffolding with actual episode packs,
MuJoCo scenarios, robot adapters, metric implementations, or aggregation logic,
update `final-rush-choices.md` and the active plan so future agents know which
launcher command and defaults are canonical.

## Suggested Lookup Order

1. Read the local repository for current files and artifacts.
2. Inspect `final-rush-choices.md` for current final-rush implementation
   decisions.
3. Inspect canonical project planning material when available.
4. Inspect relevant metric or document pages before changing derived benchmark
   content.
5. Inspect brainstorms, diagrams, or visual reasoning boards when
   reconstructing decisions or updating benchmark scope.
6. Only then update files, definitions, or implementation plans.

## Benchmark Content

Known benchmark metric topics include:

- Human-Robot Distance.
- Interaction Ratio.
- Task Success Rate.
- Path Efficiency.
- Proxemic Intrusion.

Source documents and literature-derived material should be inspected before
adding or changing benchmark claims, requirements, or metric definitions.

## Editing Expectations

- Keep benchmark definitions precise and distinguish specifications, metric
  formulas, implementation artifacts, and generated outputs.
- Prefer project-grounded changes over inventing new benchmark scope.
- Keep local-only instructions, private links, absolute paths, credentials, and
  machine-specific notes in untracked local files such as `AGENTS.md`.

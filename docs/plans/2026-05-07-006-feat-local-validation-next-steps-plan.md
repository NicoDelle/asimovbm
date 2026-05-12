---
title: "feat: Extend local validation with robot variants, real episodes, and ergonomic CLI"
type: feat
status: completed
date: 2026-05-07
origin: docs/plans/2026-05-07-005-feat-episodic-metrics-validation-loop-plan.md
related:
  - final-rush-choices.md
  - AGENTS_SHARED.md
  - examples/episode_packs/social_navigation_mvp.json
  - g1_slam/src/g1_slam/dynamic_obstacles.py
---

# feat: Extend local validation with robot variants, real episodes, and ergonomic CLI

## Summary

Extend the server-local validation harness so the same episode can run with
different robot embodiments, the two remaining MVP episodes replace smoke
overlay behavior with real scenario logic, and the CLI becomes usable enough for
manual validation without remembering long flag strings.

---

## Problem Frame

The current `local-validation` path can visibly run the first static-obstacle
episode and produce traces/placeholder metric outputs. The next blocking work
is making that harness useful for research iteration: compare embodiments such
as G1 and Go2 in the same scenario, land the dynamic-obstacle and social-cue
episodes, and remove CLI friction that makes manual validation error-prone.

---

## Requirements

- R1. The same episode pack and episode id must run with multiple robot profiles
  such as G1 and Go2 without changing scenario code.
- R2. Robot model loading must distinguish real MuJoCo assets from fallback
  marker/smoke embodiments so visual output is not misrepresented.
- R3. The second MVP episode must wrap or mirror the dynamic-obstacle logic in
  `g1_slam/src/g1_slam/dynamic_obstacles.py` through the approved
  `EpisodeScenario` interface.
- R4. The third MVP episode must implement social-cue target approach with
  target identity hidden until the cue becomes public.
- R5. All real episode implementations must emit complete per-step trace samples
  for later metric computation.
- R6. The CLI must provide ergonomic commands for common manual validation
  flows: list packs, list robots, list episodes, run one episode visibly, and
  run a robot/episode matrix.
- R7. The server-local validation boundary must remain intact: do not route this
  work through `asimovbm_client` or WebSocket transport.

---

## Scope Boundaries

- Final metric formulas and four-axis aggregation remain out of scope for this
  plan except preserving trace inputs needed by metric code.
- Full dynamic locomotion control for G1 or Go2 is out of scope unless assets
  and controllers are already available. Kinematic/mobile-base action adapters
  are acceptable if labeled clearly.
- The production client/server benchmark path is out of scope. This plan only
  concerns `--orchestrator local-validation`.
- Downloading external robot assets is not part of implementation unless the
  assets are already available locally or explicitly added as a separate setup
  step.

### Deferred to Follow-Up Work

- Dashboard presentation of robot/episode comparison results: separate UI plan.
- Final research metric formulas and trained aggregation: covered by the metric
  computation and aggregation plans.
- Physical human/obstacle MuJoCo bodies with contact-rich dynamics: only needed
  after overlay-first validation no longer satisfies metric evidence needs.

---

## Context & Research

### Relevant Code and Patterns

- `src/asimovbm_server/benchmarks/runner.py` already owns nested
  pack/tier/episode/attempt/step orchestration and metric invocation.
- `src/asimovbm_server/episodes/models.py` defines the approved
  `EpisodeScenario` protocol, public observation boundary, status semantics, and
  trace-sample contract.
- `src/asimovbm_server/episodes/static_obstacles.py` is the first concrete
  scenario replacement and is the implementation pattern to follow for scenario
  ownership, MuJoCo viewer target creation, lidar-style observation, and
  terminal evaluation.
- `g1_slam/src/g1_slam/dynamic_obstacles.py` provides the dynamic cylinder
  definitions, deterministic seeding, world bounds, and per-time obstacle pose
  logic for the second episode.
- `src/asimovbm_server/robots/registry.py` currently exposes placeholder
  `minimal-mobile-base`, `placeholder-humanoid`, and `placeholder-robot-dog`
  profiles backed by `FakeMobileBaseRobot`.
- `src/asimovbm_server/cli.py` currently exposes all validation flags on the
  top-level parser; useful behavior exists, but common runs require long
  commands.
- `docs/solutions/architecture-patterns/mujoco-server-g1-client-boundary-2026-05-06.md`
  warns against treating `g1_slam` as a server backend for the production
  client/server proof. For this plan, `g1_slam` is only a reference/source of
  scenario logic inside the server-local validation harness.

### Institutional Learnings

- Keep MuJoCo simulation authority server-owned and participant policy
  client-side for production boundary proof. The local validation path is
  explicitly separate and should stay labeled as such.
- Keep optional MuJoCo/G1 dependencies dependency-gated so pure-Python imports
  and tests do not require heavy assets.

### External References

- None used. Existing repo code and local `g1_slam` references are sufficient
  for this plan.

---

## Key Technical Decisions

- **Keep `local-validation` as the launcher:** All new flows extend the existing
  server-local runner rather than adding a second orchestration path.
- **Embodiment profiles are data/config, adapters are behavior:** Robot profiles
  should describe asset paths, embodiment kind, radius, action mode, and visual
  capabilities; adapters should own reset/apply/viewer behavior.
- **Run robot comparison as a matrix over independent episodes:** The same
  episode should be run once per selected robot profile, with separate traces
  and result records. Do not swap robots mid-episode.
- **Use overlay-first dynamic entities for episodes 2 and 3:** Dynamic humans or
  cylinders should update scenario state, observations, traces, and optional
  viewer geoms without requiring physical contacts before metrics need them.
- **Treat `g1_slam` dynamic-obstacle code as reference logic, not benchmark
  truth:** Either wrap its pure-Python objects behind scenario code or copy the
  minimal deterministic behavior locally, but keep public observation and trace
  semantics owned by `asimovbm_server`.
- **CLI ergonomics should preserve scriptability:** Prefer subcommands or clear
  validation modes with machine-readable output over interactive-only flows.

---

## Open Questions

### Resolved During Planning

- Should this use the client/server architecture? No. Per
  `final-rush-choices.md`, this remains server-local validation.
- Should real robot asset absence block episode implementation? No. Asset-backed
  profiles should be dependency-gated and clearly labeled; fallback kinematic
  profiles can keep episode work moving.

### Deferred to Implementation

- Exact Go2 asset path and model source: depends on which Unitree or local asset
  files are available in the implementation environment.
- Whether the second episode registers as `human_obstacle_navigation` or a more
  specific `dynamic_obstacle_navigation` alias: decide while integrating with
  the existing episode pack, but keep the canonical MVP tier id stable.
- Whether dynamic entities need physical MuJoCo geoms immediately or overlay
  viewer geoms are sufficient: decide from metric evidence needs and available
  viewer APIs during implementation.

---

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for
> review, not implementation specification. The implementing agent should treat
> it as context, not code to reproduce.*

```text
CLI local-validation
  -> load episode pack
  -> resolve selected episode ids
  -> resolve selected robot profiles
  -> for each robot profile:
       for each selected episode:
         scenario = ScenarioRegistry.create(definition)
         robot = RobotRegistry.create(profile)
         trace = EpisodicValidationRunner.run_episode(...)
         metrics = MetricRegistry.compute(trace) if technical_valid
  -> write result JSON with robot_profile_id per record
```

Robot profiles stay orthogonal to scenarios:

```text
EpisodeDefinition            RobotProfile
  scenario_type                id: g1-kinematic | go2-kinematic | ...
  entities/goals/cues          embodiment_kind
  max_steps/control_dt         model_path
                              body_radius
                              action_mode

Scenario owns world/entities. RobotAdapter owns robot pose/action/viewer body.
```

---

## Implementation Units

### U1. Harden Robot Profile and Model Loading

**Goal:** Allow G1 and Go2 profiles to be selected for the same episode while
clearly separating real MuJoCo assets from fallback marker embodiments.

**Requirements:** R1, R2

**Dependencies:** None

**Files:**
- Modify: `src/asimovbm_server/robots/base.py`
- Modify: `src/asimovbm_server/robots/registry.py`
- Create: `src/asimovbm_server/robots/mujoco_kinematic.py`
- Create: `examples/robot_profiles/local_validation.json`
- Test: `tests/server/test_robot_profile_loading.py`
- Test: `tests/server/test_robot_adapter_registry.py`

**Approach:**
- Introduce a robot-profile loader for repo-local profile config.
- Add explicit profiles such as `g1-kinematic`, `go2-kinematic`, and
  `minimal-mobile-base`; mark each profile as `asset_backed` or `marker_only`.
- Keep the current `[linear_velocity, yaw_rate]` action mode as the first shared
  validation action contract unless a profile declares a richer adapter.
- When an asset path is missing, fail with a setup diagnostic that names the
  missing profile and path; do not silently fall back to a cylinder for an
  asset-backed profile.
- Keep marker-only profiles available for CI and smoke tests.

**Patterns to follow:**
- `src/asimovbm_server/robots/registry.py`
- `src/asimovbm_server/simulation/mujoco_adapter.py`
- `g1_slam/src/g1_slam/mujoco_runner.py` optional asset/dependency gating

**Test scenarios:**
- Happy path: profile loader registers `minimal-mobile-base` and any configured
  local robot profiles.
- Happy path: selecting `g1-kinematic` creates an adapter with the expected body
  radius, embodiment kind, and action mode.
- Edge case: missing configured model path returns a setup error that identifies
  the profile and path.
- Error path: unknown profile id fails before the episode loop starts.
- Integration: the benchmark runner records `robot_profile_id` per episode
  trace for two different profiles run against the same episode.

**Verification:**
- A single episode can be run with at least two robot profile ids and produces
  distinct result records with correct profile metadata.

---

### U2. Add Robot/Episode Matrix Execution

**Goal:** Run selected episodes across multiple robot profiles without copying
  episode definitions or changing scenario code.

**Requirements:** R1, R6, R7

**Dependencies:** U1

**Files:**
- Modify: `src/asimovbm_server/benchmarks/models.py`
- Modify: `src/asimovbm_server/benchmarks/runner.py`
- Modify: `src/asimovbm_server/cli.py`
- Test: `tests/server/test_episodic_validation_runner.py`
- Test: `tests/server/test_local_validation_matrix.py`

**Approach:**
- Extend run config from one `robot_profile_id` to one or more selected robot
  profile ids while preserving the existing single-profile behavior.
- Execute each selected episode once per robot profile. Keep traces independent;
  do not compare or aggregate profiles inside the step loop.
- Include robot profile, embodiment kind, and asset/fallback metadata in each
  result record so later metrics and dashboards can group comparisons.
- Keep matrix execution optional; default behavior should remain one selected
  robot profile for fast manual runs.

**Patterns to follow:**
- Existing `tier_id` and `episode_id` filters in `BenchmarkRunConfig`
- `EpisodeRunRecord` result serialization in `src/asimovbm_server/benchmarks/models.py`

**Test scenarios:**
- Happy path: two robot profiles and one episode produce two records.
- Happy path: one robot profile and two selected episodes produce two records.
- Edge case: empty robot selection fails validation before any episode starts.
- Error path: one invalid profile id fails the run setup without writing a
  partial success as if the matrix were complete.
- Integration: metric registry is invoked once per technically valid
  robot/episode record.

**Verification:**
- Matrix output is deterministic and includes enough metadata to compare G1 vs
  Go2 results for the same episode id.

---

### U3. Implement Dynamic-Obstacle Episode from `g1_slam`

**Goal:** Replace the second MVP episode smoke overlay with a real dynamic
  obstacle scenario based on the existing `g1_slam` dynamic cylinder logic.

**Requirements:** R3, R5, R7

**Dependencies:** U1

**Files:**
- Create: `src/asimovbm_server/episodes/dynamic_obstacles.py`
- Modify: `src/asimovbm_server/episodes/registry.py`
- Modify: `examples/episode_packs/social_navigation_mvp.json`
- Test: `tests/server/test_dynamic_obstacle_scenario.py`
- Reference: `g1_slam/src/g1_slam/dynamic_obstacles.py`
- Reference: `g1_slam/tests/test_navigation.py`

**Approach:**
- Implement an `EpisodeScenario` that creates deterministic moving entities
  using the same parameters and seed behavior as `make_default_dynamic_cylinders`.
- Update entity positions in `before_step(time_s, world)`.
- Emit moving entities as public observations and trace samples with position,
  radius, role/kind, and velocity metadata sufficient for interaction and
  proxemic metrics.
- Terminate on success, timeout, collision/proxemic violation, or technical
  failure using the shared `EpisodeStatusCode` values.
- Provide a MuJoCo viewer target or viewer overlay update so manual validation
  shows moving cylinders/humans rather than only trace JSON.

**Patterns to follow:**
- `src/asimovbm_server/episodes/static_obstacles.py`
- `src/asimovbm_server/episodes/overlay.py`
- `g1_slam/src/g1_slam/dynamic_obstacles.py`

**Test scenarios:**
- Happy path: dynamic scenario reset emits the configured start pose, goal, and
  deterministic dynamic entities.
- Happy path: the same seed yields identical entity positions at several times.
- Edge case: changing seed changes at least one entity phase/trajectory while
  preserving entity ids and count.
- Error path: collision with a dynamic entity returns the expected terminal
  status and keeps `technical_valid=True`.
- Integration: runner trace includes dynamic entity positions and velocities at
  every step.

**Verification:**
- Running the `human_obstacles` tier visibly shows moving entities and produces
  a technically valid trace with non-empty dynamic entity samples.

---

### U4. Implement Social-Cue Target Episode

**Goal:** Replace the third MVP episode smoke overlay with a scenario where the
  robot navigates among humans and approaches the target only after a public
  social cue.

**Requirements:** R4, R5, R7

**Dependencies:** U3

**Files:**
- Create: `src/asimovbm_server/episodes/social_cue_target.py`
- Modify: `src/asimovbm_server/episodes/registry.py`
- Modify: `examples/episode_packs/social_navigation_mvp.json`
- Test: `tests/server/test_social_cue_target_scenario.py`
- Test: `tests/server/test_episode_pack_loader.py`

**Approach:**
- Implement cue scheduling inside scenario state. Before cue time, the target
  identity must not be exposed through `public_goal.target_human_id` or public
  entity role.
- At cue time, emit a `PublicCueEvent`, reveal the public target identity, and
  allow the agent to approach within `stop_distance_m`.
- Trace every human with stable id, pose, radius, role, posture, and public
  visibility state.
- Evaluate success based on stopping within target distance after the cue,
  not merely reaching a coordinate.
- Keep hidden/future cue schedule out of `EpisodeObservation` while preserving
  full trace evidence for metrics after the episode.

**Patterns to follow:**
- `src/asimovbm_server/episodes/models.py` observation boundary
- `src/asimovbm_server/episodes/overlay.py` cue/event scaffolding
- `final-rush-choices.md` hidden-state and cue visibility rules

**Test scenarios:**
- Happy path: before cue time, the observation includes humans but does not
  expose target identity.
- Happy path: at or after cue time, the observation emits the cue and exposes
  the target in public goal/entity role.
- Happy path: stopping within `stop_distance_m` after the cue returns success.
- Edge case: reaching the target location before cue does not count as social
  cue success.
- Error path: missing cue source in episode pack validation fails clearly.
- Integration: trace contains cue event timing, target id, robot stop pose, and
  terminal status for metric computation.

**Verification:**
- Running the `social_cue_target` tier visibly shows the target/bystander setup,
  cue emission in trace output, and a terminal status based on target approach.

---

### U5. Improve Built-In Validation Policies for MVP Episodes

**Goal:** Ensure manual validation episodes demonstrate the intended scenario
  mechanics before research policies are plugged in.

**Requirements:** R3, R4, R5

**Dependencies:** U3, U4

**Files:**
- Modify: `src/asimovbm_server/agents/obstacle_aware_navigation.py`
- Create: `src/asimovbm_server/agents/social_cue_navigation.py`
- Modify: `src/asimovbm_server/agents/registry.py`
- Test: `tests/server/test_obstacle_aware_navigation_policy.py`
- Test: `tests/server/test_social_cue_navigation_policy.py`

**Approach:**
- Keep policies simple and deterministic; they are validation agents, not
  research baselines.
- Extend obstacle-aware behavior to account for moving public entities using
  current public observations only.
- Add a social-cue-aware policy that waits or navigates generically before cue
  reveal, then targets the revealed public target id.
- Never give validation policies hidden cue schedule, hidden target identity, or
  metric thresholds.

**Patterns to follow:**
- `src/asimovbm_server/agents/base.py`
- `src/asimovbm_server/agents/obstacle_aware_navigation.py`

**Test scenarios:**
- Happy path: dynamic-obstacle policy produces finite actions that change as
  visible entity positions move.
- Happy path: social-cue policy does not target hidden human id before cue.
- Happy path: social-cue policy targets revealed public target after cue.
- Edge case: no public goal produces a stop action rather than an exception.
- Integration: built-in policy can complete at least one deterministic smoke run
  for each MVP tier, or returns a behavioral failure with complete trace data.

**Verification:**
- Built-in policies are good enough to visually validate each episode mechanic
  without claiming they are final benchmark agents.

---

### U6. Make the CLI Ergonomic

**Goal:** Make common validation workflows discoverable and short to run.

**Requirements:** R6, R7

**Dependencies:** U1, U2

**Files:**
- Modify: `src/asimovbm_server/cli.py`
- Create: `src/asimovbm_server/validation_cli.py`
- Test: `tests/server/test_cli_local_validation.py`
- Update: `docs/run-g1-slam-episode.md`
- Create: `docs/run-local-validation.md`

**Approach:**
- Keep backward-compatible top-level flags where practical, but add a clearer
  validation-focused surface.
- Add list commands for episode packs, episodes, tiers, robot profiles, and
  agent profiles.
- Add a short visible-run command path for the common case: selected tier,
  selected episode, selected robot, selected agent, and artifact root.
- Add matrix flags for multiple robot profiles and optional machine-readable
  JSON summary output.
- Make GUI requirements explicit: `--visible`, `--realtime`, and Wayland/X11
  guidance belong in docs and help text.

**Patterns to follow:**
- Existing `argparse` style in `src/asimovbm_server/cli.py`
- Artifact output from `write_result_json`

**Test scenarios:**
- Happy path: `--help` includes local-validation examples or subcommands.
- Happy path: list robots returns registered profile ids without launching a
  simulation.
- Happy path: list episodes returns tier ids, episode ids, and scenario types
  from the selected pack.
- Happy path: visible-run flags map to the same `BenchmarkRunConfig` fields as
  the existing long command.
- Edge case: invalid tier/episode/profile fails with actionable text before
  opening a viewer.
- Integration: matrix CLI produces result JSON with one record per
  robot/episode combination.

**Verification:**
- A teammate can discover and run the three common flows from `--help` and
  `docs/run-local-validation.md`: list, visible single episode, matrix run.

---

### U7. Update Canonical Rush Docs and Handoffs

**Goal:** Keep future agents from confusing smoke scaffolding, real episode
  implementations, robot assets, and canonical commands.

**Requirements:** R2, R3, R4, R6, R7

**Dependencies:** U1, U3, U4, U6

**Files:**
- Modify: `final-rush-choices.md`
- Modify: `docs/plans/2026-05-07-005-feat-episodic-metrics-validation-loop-plan.md`
- Modify: `docs/run-local-validation.md`
- Test: none

**Approach:**
- Record which scenario registrations are real and which remain smoke.
- Record canonical robot profile ids and whether they are asset-backed or
  marker-only.
- Record the canonical CLI commands for a visible single episode and matrix
  validation run.
- Keep the server-local validation boundary explicit.

**Patterns to follow:**
- Current `final-rush-choices.md` replacement notes for
  `obstacle_navigation`
- Current "Current Launcher and Handoff Instructions" section in the active
  episodic-loop plan

**Test scenarios:**
- Test expectation: none -- documentation-only handoff update.

**Verification:**
- Future agents can identify the current launcher, real scenario classes,
  remaining smoke scaffolding, and expected replacement work without asking
  Nico to reconstruct context.

---

## System-Wide Impact

- **Interaction graph:** The work touches CLI setup, robot registry/profile
  resolution, scenario registry, benchmark runner loops, trace serialization,
  and metric invocation. The step-loop order should remain unchanged.
- **Error propagation:** Missing robot assets, unknown profiles, invalid episode
  ids, and invalid scenario configs should fail at setup with actionable errors.
  Runtime policy/scenario failures should still become technical episode
  failures in traces.
- **State lifecycle risks:** Each robot/profile/episode matrix item must create
  fresh robot, agent, scenario, and world state. Reusing scenario state across
  matrix runs would corrupt traces.
- **API surface parity:** CLI defaults and docs must stay synchronized with
  `BenchmarkRunConfig`; changing one without the other will confuse teammates.
- **Integration coverage:** Unit tests should prove scenario behavior; runner
  integration tests should prove robot/profile matrix accounting and metric
  invocation.
- **Unchanged invariants:** `local-validation` must not import
  `asimovbm_client`; metric functions consume traces after technically valid
  episodes; policies consume only public observations.

---

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Go2 assets are not locally available | Make asset-backed profile loading explicit and dependency-gated; keep marker-only profile for smoke runs. |
| Dynamic-obstacle code drifts from `g1_slam` reference | Add deterministic seed/position tests against expected positions or imported pure-Python reference values. |
| CLI grows into another architecture | Keep `local-validation` as the orchestrator and route CLI options into `BenchmarkRunConfig` rather than adding a separate runner. |
| Social-cue scenario leaks hidden target identity | Add pre-cue/post-cue observation tests and trace-only hidden-state assertions. |
| Matrix execution hides per-profile failures | Store one record per robot/episode attempt with profile id and terminal status; do not collapse failures before writing artifacts. |

---

## Documentation / Operational Notes

- `docs/run-local-validation.md` should become the canonical manual runbook.
- `docs/run-g1-slam-episode.md` should either point to the new runbook or be
  narrowed to pure `g1_slam` demo usage.
- Help text should include at least one visible first-episode command and one
  matrix command.
- When an implementation replaces smoke scaffolding, update
  `final-rush-choices.md` in the same PR.

---

## Sources & References

- Origin plan: `docs/plans/2026-05-07-005-feat-episodic-metrics-validation-loop-plan.md`
- Rush decisions: `final-rush-choices.md`
- Shared agent instructions: `AGENTS_SHARED.md`
- Current episode pack: `examples/episode_packs/social_navigation_mvp.json`
- Static scenario pattern: `src/asimovbm_server/episodes/static_obstacles.py`
- Dynamic obstacle reference: `g1_slam/src/g1_slam/dynamic_obstacles.py`
- Scenario contract: `src/asimovbm_server/episodes/models.py`
- Runner: `src/asimovbm_server/benchmarks/runner.py`
- CLI: `src/asimovbm_server/cli.py`
- Boundary learning: `docs/solutions/architecture-patterns/mujoco-server-g1-client-boundary-2026-05-06.md`

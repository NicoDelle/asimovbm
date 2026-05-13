---
title: "feat: Normalize RoboJudo episodes into server-local validation"
type: feat
status: completed
date: 2026-05-12
origin: docs/plans/2026-05-07-006-feat-local-validation-next-steps-plan.md
---

# feat: Normalize RoboJudo episodes into server-local validation

## Summary

Normalize the RoboJudo demo work into the existing server-local validation
architecture by turning robot-specific demo configs into robot-neutral episodes,
preserving rectangular simulation geometry, and limiting RoboJudo itself to
robot backend loading and stepping. The centralized episode runner remains the
owner of episode loading, sequencing, trace collection, and metric handoff.

---

## Problem Frame

The current local-validation harness has the right orchestration boundary, but
the newer RoboJudo work in `g1_slam` is still shaped as runnable demos: each
config combines scenario geometry, robot identity, locomotion policy, controller
parameters, visualization, and the episode loop. For the benchmark testbench,
those pieces need to be dismembered into server-owned episode scenarios,
swappable robot adapters, and reusable policies.

---

## Requirements

- R1. The server-local validation runner must remain the centralized episode
  manager: it loads episode packs, runs selected episodes sequentially by
  default, records traces, and hands technically valid traces to metric code.
- R2. RoboJudo-specific code must be narrowed to robot/backend setup and
  stepping; it must not own the benchmark episode loop, metric computation, or
  final trace format.
- R3. Robot-specific RoboJudo demo configs must normalize into robot-neutral
  episode definitions plus separate robot/profile and policy/profile metadata.
- R4. Static obstacles must be represented as rectangles matching the MuJoCo
  simulation geometry, not lossy circular approximations.
- R5. The first adapted episode must be tightened first so it establishes the
  rectangle/entity/trace pattern for the remaining episodes.
- R6. The second dynamic-obstacle episode must use the same normalized scenario
  pattern, including static rectangles, moving entities, public observations,
  and complete per-step trace samples.
- R7. The third social-cue episode must stay compatible with the same robot
  profile matrix and central runner, even if RoboJudo does not currently provide
  a native social-cue demo source.
- R8. All normalized episodes must remain runnable through the ergonomic
  local-validation CLI and produce result records that identify episode id,
  robot profile id, adapter/backend kind, terminal status, and metric inputs.

---

## Scope Boundaries

- This plan does not implement final research metric formulas or learned
  aggregation.
- This plan does not make RoboJudo a server backend for the production
  WebSocket/client benchmark path; it is only a robot adapter option inside
  server-local validation.
- This plan does not require downloading external G1 assets or RoboJudo itself.
  Missing asset-backed profiles should fail with setup diagnostics or remain
  explicitly unavailable.
- This plan does not require physical contact-rich human bodies. Overlay-first
  entities are acceptable when they emit observations and trace evidence.
- This plan does not delete
  `docs/plans/2026-05-07-006-feat-local-validation-next-steps-plan.md`; that
  completed plan remains historical context.

### Deferred to Follow-Up Work

- Full production client/server benchmark execution with real robot package
  submission.
- Dashboard presentation for episode x robot comparison results.
- Physical dynamic-human or obstacle contacts after overlay-first evidence no
  longer satisfies the metric needs.

---

## Context & Research

### Relevant Code and Patterns

- `src/asimovbm_server/benchmarks/runner.py` already owns the pack/tier/episode
  loop, robot profile matrix, trace creation, visible viewer lifecycle, and
  metric invocation.
- `src/asimovbm_server/episodes/models.py` defines the `EpisodeDefinition`,
  public observation, status, and `EpisodeScenario` protocol that normalized
  episodes must satisfy.
- `src/asimovbm_server/episodes/static_obstacles.py` already contains a
  rectangle-based world internally, but the pack format still describes
  obstacles mostly as radius entities.
- `src/asimovbm_server/episodes/dynamic_obstacles.py` mirrors the deterministic
  `g1_slam` dynamic cylinder behavior and emits moving public entities.
- `src/asimovbm_server/robots/base.py` and
  `src/asimovbm_server/robots/registry.py` provide the current robot profile and
  adapter seams.
- `g1_slam/config/episodes/*.json` contains six RoboJudo/Go2 demo configs:
  approach-user, lateral-open, and lateral-static-dynamic-obstacles for G1 and
  Go2.
- `g1_slam/src/g1_slam/robojudo_backend.py` currently owns backend setup,
  planner/controller/lidar stepping, dynamic cylinder placement, success
  detection, and printing. The plan should reuse backend capabilities without
  preserving this ownership shape.

### Institutional Learnings

- `AGENTS_SHARED.md` and `final-rush-choices.md` require the local-validation
  boundary to stay server-local and require `final-rush-choices.md` updates when
  canonical episodic validation behavior changes.
- `AGENTS.md` requires Python tests to run with `.venv/bin/python -m pytest ...`
  and forbids `pip` outside the repo virtualenv.

### External References

- None. Local code and the existing RoboJudo demo files are sufficient for this
  planning pass.

---

## Key Technical Decisions

- Keep scenario data robot-neutral: normalize `g1_*` and `go2_*` demo configs
  into shared episode ids and put robot/backend differences into robot profiles
  and policy profiles.
- Make rectangular obstacle geometry first-class in local validation. Existing
  circular public entities can remain as a coarse observation projection, but
  traces and collision logic need the simulation rectangle extents.
- Treat RoboJudo as a robot adapter, not as an episode runner. The adapter may
  wrap the RoboJudo pipeline, virtual joystick, and pose extraction, but the
  server runner still calls `apply_action()`, records `RobotState`, and owns
  terminal status.
- Preserve sequential execution as the default. Concurrency is not needed for
  MVP validation and would make visible manual inspection harder.
- Keep fallback/kinematic profiles available. Asset-backed RoboJudo/G1 profiles
  should be honest about missing dependencies instead of silently pretending to
  be real.

---

## Open Questions

### Resolved During Planning

- Should the completed local-validation plan be updated in place? No. Create a
  new follow-up plan and carry forward useful decisions.
- Should obstacles be circles or rectangles? Rectangles should be the source of
  truth because they match the simulation geometry.
- Should RoboJudo own episode lifecycle? No. It should only own loading and
  stepping the robot backend.

### Deferred to Implementation

- Exact RoboJudo dependency availability and G1 policy asset path: implementation
  should detect local availability and fail clearly for missing asset-backed
  profiles.
- Exact normalized episode ids: implementation should choose concise canonical
  ids, while preserving old demo ids as metadata or aliases when useful for
  trace provenance.
- Whether the Go2 policy backend can be wrapped in the same adapter shape as
  RoboJudo immediately or should remain kinematic until the profile is stable.

---

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for
> review, not implementation specification. The implementing agent should treat
> it as context, not code to reproduce.*

```text
RoboJudo demo config
  -> normalized scenario data
       episode id, start, goal, bounds, rectangular obstacles,
       dynamic obstacle settings, cue schedule if present
  -> robot profile data
       robot id, backend kind, model/policy paths, body radius, setup checks
  -> agent profile data
       controller family, speed limits, waypoint tolerances

EpisodicValidationRunner
  for each selected episode:
    for each selected robot profile:
      scenario = ScenarioRegistry.create(episode)
      robot = RobotRegistry.create(profile)
      agent = AgentRegistry.create(policy)
      step sequentially, record EpisodeTrace, then compute metrics
```

---

## Implementation Units

### U1. Add Rectangular Entity Support to Episode Definitions

**Goal:** Make rectangular obstacle geometry a first-class validation input so
the scenario, MuJoCo visualization, collision checks, and traces use the same
shape as the simulation.

**Requirements:** R4, R5, R6

**Dependencies:** None

**Files:**
- Modify: `src/asimovbm_server/episodes/models.py`
- Modify: `src/asimovbm_server/episodes/loader.py`
- Modify: `src/asimovbm_server/episodes/static_obstacles.py`
- Modify: `src/asimovbm_server/episodes/dynamic_obstacles.py`
- Test: `tests/server/test_episode_pack_loader.py`
- Test: `tests/server/test_static_obstacle_scenario.py`
- Test: `tests/server/test_dynamic_obstacle_scenario.py`

**Approach:**
- Extend entity metadata or the formal entity model so obstacles can describe
  rectangle extents without relying on `radius` as the source of truth.
- Keep `radius` available as a coarse public observation field and conservative
  collision envelope where consumers expect it.
- Ensure trace metadata includes exact rectangle extents for metric consumers.
- Keep pack validation strict enough to reject malformed rectangles.

**Execution note:** Start with loader/scenario characterization tests for a
rectangular obstacle pack before changing scenario behavior.

**Patterns to follow:**
- `src/asimovbm_server/episodes/static_obstacles.py`
- `g1_slam/src/g1_slam/world.py`
- `g1_slam/config/episodes/g1_lateral_static_dynamic_obstacles.json`

**Test scenarios:**
- Happy path: a pack with rectangular obstacle extents loads into an
  `EpisodeDefinition` and produces matching static-world rectangles.
- Happy path: static scenario collision uses rectangle extents plus robot radius,
  not only the entity center/radius.
- Happy path: trace samples include rectangle extents for each static obstacle.
- Edge case: an obstacle with invalid rectangle bounds fails pack validation
  with an actionable error.
- Integration: MuJoCo scene generation uses the same rectangle extents as the
  collision world.

**Verification:**
- First-episode obstacles can be represented from the same rectangle data that
  would be placed in a MuJoCo world.

---

### U2. Normalize the First Static-Obstacle Episode

**Goal:** Adjust the first adapted episode to use the new rectangular obstacle
contract and establish the source-of-truth pattern for later episodes.

**Requirements:** R1, R4, R5, R8

**Dependencies:** U1

**Files:**
- Modify: `examples/episode_packs/social_navigation_mvp.json`
- Modify: `docs/run-local-validation.md`
- Modify: `final-rush-choices.md`
- Test: `tests/server/test_static_obstacle_scenario.py`
- Test: `tests/server/test_local_validation_matrix.py`

**Approach:**
- Convert `obstacle_slalom_001` from radius-only obstacle entries to rectangle
  geometry matching the intended simulation layout.
- Preserve public observations and current policy compatibility by projecting
  rectangles to visible entities with stable ids, radii, and metadata.
- Keep the episode robot-neutral; run it through the existing robot profile
  matrix without changing scenario code.

**Patterns to follow:**
- `examples/episode_packs/social_navigation_mvp.json`
- `src/asimovbm_server/benchmarks/runner.py`

**Test scenarios:**
- Happy path: `obstacle_slalom_001` loads with rectangular obstacles and runs
  through the matrix with `minimal-mobile-base` and `g1-kinematic`.
- Happy path: the first step trace contains exact rectangle metadata for every
  static obstacle.
- Edge case: policy observations still expose enough coarse obstacle data for
  the existing obstacle-aware agent to act.
- Integration: result records still include robot profile metadata and
  technically valid traces.

**Verification:**
- The first episode becomes the canonical example of scenario-owned rectangle
  geometry plus robot-profile swapping.

---

### U3. Normalize RoboJudo Demo Configs into Robot-Neutral Episodes

**Goal:** Convert the G1/Go2-specific RoboJudo demo configs into shared server
episode definitions without embedding locomotion or policy ownership in the
episode itself.

**Requirements:** R1, R3, R8

**Dependencies:** U1

**Files:**
- Create: `examples/episode_packs/robojudo_navigation_validation.json`
- Create or modify: `src/asimovbm_server/episodes/robojudo_config_normalizer.py`
- Test: `tests/server/test_robojudo_episode_normalization.py`

**Approach:**
- Normalize matching G1/Go2 demo pairs into shared episode ids such as
  approach-user, lateral-open, and lateral-static-dynamic-obstacles.
- Carry original config ids, source file names, visualization hints, and
  controller defaults as metadata or profile references, not as separate
  scenario definitions.
- Preserve rectangular world obstacles exactly for obstacle-bearing episodes.
- Do not require RoboJudo dependencies to import or load the normalized episode
  pack.

**Patterns to follow:**
- `src/asimovbm_server/episodes/loader.py`
- `g1_slam/src/g1_slam/config.py`
- `g1_slam/config/episodes/*.json`

**Test scenarios:**
- Happy path: the normalizer collapses G1/Go2 lateral-open configs into one
  robot-neutral episode with source provenance metadata.
- Happy path: obstacle-bearing RoboJudo configs produce rectangular obstacle
  definitions matching their source bounds.
- Edge case: mismatched paired configs preserve the conflict as a validation
  diagnostic instead of silently picking one robot's geometry.
- Error path: a malformed RoboJudo config fails before writing or loading an
  invalid server episode.

**Verification:**
- Normalized packs can be loaded by `load_episode_pack()` and listed by the
  local-validation CLI without importing RoboJudo.

---

### U4. Adapt the Second Dynamic-Obstacle Episode to the Normalized Pattern

**Goal:** Bring the second episode onto the same rectangle-aware, robot-neutral
scenario contract while preserving moving obstacle traces.

**Requirements:** R1, R4, R6, R8

**Dependencies:** U1, U3

**Files:**
- Modify: `src/asimovbm_server/episodes/dynamic_obstacles.py`
- Modify: `examples/episode_packs/social_navigation_mvp.json`
- Modify: `examples/episode_packs/robojudo_navigation_validation.json`
- Test: `tests/server/test_dynamic_obstacle_scenario.py`
- Test: `tests/server/test_local_validation_matrix.py`

**Approach:**
- Allow dynamic-obstacle scenarios to combine static rectangular obstacles with
  moving cylinder/human entities.
- Keep moving entities as public observations with velocity, role, radius, and
  metadata on every step.
- Ensure static rectangles and moving entities both appear in trace samples so
  later metrics can compute safety, path efficiency, and interaction evidence.
- Keep the episode definition independent of G1/Go2, with robot differences
  supplied by the matrix.

**Patterns to follow:**
- `src/asimovbm_server/episodes/dynamic_obstacles.py`
- `g1_slam/src/g1_slam/dynamic_obstacles.py`
- `g1_slam/config/episodes/g1_lateral_static_dynamic_obstacles.json`

**Test scenarios:**
- Happy path: dynamic scenario emits static rectangle metadata and moving entity
  observations in the same step trace.
- Happy path: deterministic seed/count produces stable dynamic cylinder ids and
  trajectories.
- Edge case: robot collision with a static rectangle and collision with a moving
  entity are distinguished in collision summaries.
- Integration: normalized dynamic episode runs for two robot profiles and
  produces separate result records with complete trace data.

**Verification:**
- The second episode behaves like a normal server-owned scenario, not a
  RoboJudo-owned demo loop.

---

### U5. Add RoboJudo-Backed Robot/Profile Seam

**Goal:** Introduce RoboJudo as an optional robot adapter that satisfies the
server `RobotAdapter` contract without taking over the episode lifecycle.

**Requirements:** R2, R3, R8

**Dependencies:** U3

**Files:**
- Create: `src/asimovbm_server/robots/robojudo_adapter.py`
- Modify: `src/asimovbm_server/robots/base.py`
- Modify: `src/asimovbm_server/robots/registry.py`
- Modify: `examples/robot_profiles/local_validation.json`
- Test: `tests/server/test_robot_profile_loading.py`
- Test: `tests/server/test_robojudo_robot_adapter.py`

**Approach:**
- Add profile metadata for RoboJudo-backed G1 and, if appropriate, policy-backed
  Go2 profiles while preserving kinematic fallbacks.
- The adapter should expose reset/state/apply-action/viewer-target semantics
  like existing robot adapters.
- Missing RoboJudo repo, missing G1 policy, or missing model assets should
  produce setup diagnostics and should not silently fall back to marker-only
  behavior for asset-backed profiles.
- Keep RoboJudo imports dependency-gated so pure local-validation tests and pack
  loading do not require RoboJudo to be installed.

**Patterns to follow:**
- `src/asimovbm_server/robots/mujoco_kinematic.py`
- `g1_slam/src/g1_slam/robojudo_backend.py`
- `src/asimovbm_server/robots/registry.py`

**Test scenarios:**
- Happy path: registry exposes RoboJudo-backed profile metadata without
  importing RoboJudo.
- Error path: creating an asset-backed RoboJudo profile with missing
  dependencies fails with a diagnostic naming the profile and missing resource.
- Happy path with fakes: a fake RoboJudo backend can be stepped through the
  `RobotAdapter` contract and returns `RobotState` with pose, velocity, and
  metadata.
- Integration: local-validation can select kinematic profiles even when
  RoboJudo is unavailable.

**Verification:**
- RoboJudo is reduced to a swappable robot backend and no scenario code depends
  on RoboJudo directly.

---

### U6. Keep the Third Social-Cue Episode Robot-Neutral

**Goal:** Ensure the third MVP episode fits the same normalized manager/profile
shape even though the current RoboJudo demo set does not include a native social
cue target scenario.

**Requirements:** R1, R7, R8

**Dependencies:** U1, U5

**Files:**
- Modify: `src/asimovbm_server/episodes/social_cue_target.py`
- Modify: `examples/episode_packs/social_navigation_mvp.json`
- Test: `tests/server/test_social_cue_target_scenario.py`
- Test: `tests/server/test_social_cue_navigation_policy.py`
- Test: `tests/server/test_local_validation_matrix.py`

**Approach:**
- Preserve target-hidden-until-cue semantics and ensure all public observations
  remain independent of robot profile.
- Add any needed rectangle-aware environmental context without exposing hidden
  cue schedules or target identity to policies.
- Run this episode through the same robot-profile matrix as the first two
  episodes, using available kinematic/RoboJudo profiles depending on setup.

**Patterns to follow:**
- `src/asimovbm_server/episodes/social_cue_target.py`
- `src/asimovbm_server/episodes/models.py`
- `final-rush-choices.md`

**Test scenarios:**
- Happy path: before the cue, the target appears only as a public human and the
  public goal remains hidden.
- Happy path: after the cue, target identity and public goal become visible and
  success is evaluated by stop distance.
- Edge case: reaching the target location before the cue does not count as
  success.
- Integration: the social-cue episode runs under at least two robot profiles
  without scenario code branching on robot id.

**Verification:**
- The third episode remains a benchmark scenario rather than a robot-specific
  demo script.

---

### U7. Wire Sequential Pack Execution, CLI, and Docs

**Goal:** Make the normalized episodes discoverable and runnable as a sequential
testbench flow for visualization and metric handoff.

**Requirements:** R1, R8

**Dependencies:** U2, U3, U4, U5, U6

**Files:**
- Modify: `src/asimovbm_server/validation_cli.py`
- Modify: `docs/run-local-validation.md`
- Modify: `docs/run-g1-slam-episode.md`
- Modify: `final-rush-choices.md`
- Test: `tests/server/test_local_validation_matrix.py`
- Test: `tests/server/test_robot_profile_loading.py`

**Approach:**
- Ensure the CLI can list and run the normalized RoboJudo validation pack
  without manual path spelunking.
- Keep sequential execution as the documented default for visible validation.
- Document which profiles are real asset-backed, which are kinematic fallback,
  and which require external setup.
- Record the normalized episode ids and canonical local-validation commands in
  `final-rush-choices.md`.

**Patterns to follow:**
- `src/asimovbm_server/validation_cli.py`
- `docs/run-local-validation.md`

**Test scenarios:**
- Happy path: list commands show normalized episodes and robot profiles.
- Happy path: a full sequential run over selected normalized episodes writes a
  result JSON with one record per episode/profile combination.
- Error path: selecting an unavailable RoboJudo profile fails before the episode
  loop with actionable setup diagnostics.
- Integration: the CLI can still run the existing MVP pack after adding the
  normalized RoboJudo pack.

**Verification:**
- A reviewer can run the local testbench sequentially and see trace artifacts
  suitable for metric consumers.

---

## System-Wide Impact

- **Interaction graph:** Episode packs, scenario registry, robot registry, agent
  registry, validation CLI, trace models, and documentation all participate in
  this change.
- **Error propagation:** Missing assets or dependencies should surface as setup
  diagnostics before or at robot creation, not as mid-episode technical
  failures unless the backend fails while stepping.
- **State lifecycle risks:** RoboJudo backend state must reset per episode and
  per attempt so matrix records remain independent.
- **API surface parity:** The top-level legacy `--orchestrator local-validation`
  path should keep working, but new docs should prefer local-validation
  subcommands.
- **Integration coverage:** Unit tests should cover loaders and scenarios; CLI
  or runner-level tests should prove pack/profile matrix behavior.
- **Unchanged invariants:** Metric computation continues to consume
  `EpisodeTrace`; production WebSocket/client benchmark flow remains out of
  scope.

---

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| RoboJudo dependencies or G1 assets are missing locally | Dependency-gate imports and expose setup diagnostics; keep kinematic profiles runnable. |
| Normalizing G1/Go2 configs hides real robot-specific differences | Preserve robot-specific controller/policy settings in profile or agent metadata and keep source config provenance in traces. |
| Rectangle support breaks existing circular obstacle tests | Maintain public `radius` projection while making rectangle extents the collision/trace source of truth. |
| Scenario code starts depending on RoboJudo details | Keep RoboJudo only in `robots/` adapter code and assert pack/scenario loading works without RoboJudo installed. |
| Visible sequential runs become too slow with real RoboJudo | Keep default kinematic smoke profiles and document real-profile setup separately. |

---

## Documentation / Operational Notes

- Update `final-rush-choices.md` when canonical episode ids, robot profiles, or
  CLI commands change.
- Keep `docs/run-local-validation.md` as the canonical runbook for server-local
  validation and leave `docs/run-g1-slam-episode.md` focused on the standalone
  `g1_slam` demo path.
- Test execution should use `.venv/bin/python -m pytest ...`; do not use `pip`
  outside the repo virtualenv.

---

## Sources & References

- Prior plan: `docs/plans/2026-05-07-006-feat-local-validation-next-steps-plan.md`
- Final-rush decisions: `final-rush-choices.md`
- Current MVP pack: `examples/episode_packs/social_navigation_mvp.json`
- Robot profiles: `examples/robot_profiles/local_validation.json`
- RoboJudo demo configs: `g1_slam/config/episodes/*.json`
- RoboJudo backend source: `g1_slam/src/g1_slam/robojudo_backend.py`
- Server runner: `src/asimovbm_server/benchmarks/runner.py`
- Episode contracts: `src/asimovbm_server/episodes/models.py`

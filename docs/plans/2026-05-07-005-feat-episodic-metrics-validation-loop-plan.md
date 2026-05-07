---
title: "feat: Build episodic metrics validation loop"
type: feat
status: active
date: 2026-05-07
branch: paper-sub
origin: docs/specs/social-navigation-metrics.md
related:
  - final-rush-choices.md
  - docs/specs/social-navigation-metrics.md
  - docs/plans/2026-05-07-002-feat-social-navigation-feature-computation-plan.md
---

# feat: Build episodic metrics validation loop

## Summary

Build a server-side episodic benchmark loop for validating the social-navigation
environment and metric interfaces. This branch should stop treating the client
transport as the proof path: the validation runner should load interchangeable
robot embodiments and local agent policies, run nested benchmark/tier/episode/
step loops, record complete traces, optionally render visible simulation, and
call metric functions through a stable interface.

The metric formulas can be implemented in a second pass. The first pass must
make metric computation easy by producing the right `EpisodeTrace` data and by
calling placeholder metric modules through the same interface the real metric
engines will use.

## Problem Frame

The current codebase proves pieces of the architecture: protocol exchange,
MuJoCo stepping, and open-loop parity. It does not yet provide a clean
benchmark-runner structure for repeated episodes, tier accounting, robot-body
swapping, or metric validation.

For metric development, the client/server boundary is mostly noise. We need a
fast local harness where researchers can load an environment, choose a robot
embodiment such as a humanoid or robot dog, plug in an agent policy, run the
same episode packs repeatedly, visualize what happened, and inspect metric
inputs/outputs. The production black-box client path can reuse the same episode
and metric core later, but this branch should optimize for validating episodes
and metrics.

## Scope

In scope:

- A nested episodic loop:
  benchmark run -> tier -> episode attempt -> control step -> trace -> metrics.
- Server/local agent interface that bypasses `asimovbm_client` and WebSockets.
- Episode pack loading from versioned config files.
- Robot embodiment loading with swappable MuJoCo assets and action adapters.
- Agent policy loading with interchangeable local policies.
- Visible simulation support for manual validation.
- A typed episode trace model designed for metric functions.
- A metric registry/interface with placeholder modules.
- Tests that verify loop nesting, trace completeness, and metric invocation.

Out of scope:

- Removing the client package from the repository.
- Final metric formulas and calibrated aggregation.
- Full hosted dashboard integration.
- Remote participant policy execution.
- Perfect humanoid/dog locomotion controllers. The first embodiment adapters may
  expose a shared mobile-base smoke action until richer control contracts land.

## Requirements Trace

- R1. The validation runner must execute episodes without using the client
  transport stack.
- R2. The loop must support nested benchmark/tier/episode/step execution.
- R3. Episode packs must be loadable and extensible so colleagues can add tiers
  or scenarios in parallel.
- R4. Robot embodiments must be interchangeable, including future humanoid and
  robot-dog assets.
- R5. Agent policies must be interchangeable independently of robot embodiment
  and episode pack.
- R6. Every episode must produce a complete trace suitable for later metric
  computation.
- R7. Metric computation must be represented by a stable callable interface even
  when the first modules are placeholders.
- R8. Simulation must be viewable or recordable for manual validation.
- R9. Technical failures and behavioral failures must remain separate.

## Key Decisions

- **Final-rush choices are binding.** Check `final-rush-choices.md` before
  implementing or changing the episode contract, observation boundary, status
  semantics, trace schema, metric invocation, or aggregation behavior.
- **Validation path is server-local.** Do not route this runner through
  `asimovbm_client`, `StepSynchronousRunner`, or WebSocket transport. Keep the
  production client path available, but this branch is for local episode/metric
  validation.
- **Visible MuJoCo is required for MVP validation.** The first acceptance path
  must open a MuJoCo viewer and visibly run the MVP episode sequence. Headless
  execution can exist for CI, but it is not enough for the manual research
  validation loop.
- **Episode core before metric formulas.** Implement the loop, trace model, and
  metric call boundary first. Placeholder metric functions should fail loudly
  only when required trace fields are missing.
- **Data-driven episode packs.** Define scenario/tier/episode configs in files
  so different people can add episodes without touching runner code.
- **Embodiment adapters own robot specifics.** The runner should see a common
  `RobotAdapter` surface. Humanoid, quadruped, and mobile-base details stay in
  adapter modules.
- **Agent policies consume observations, not hidden state.** Even without the
  client transport, local agents should receive the same public observation
  object that a remote policy would get.
- **Metrics consume traces, not live simulation state.** Metric functions should
  be pure with respect to an `EpisodeTrace` plus metric/scenario constants.

## Episode Interface for Parallel Work

An episode should be a declarative scenario contract plus a small lifecycle
interface. It should not own the benchmark loop, the metric registry, the agent,
or the viewer. That keeps colleague-owned scenario work independent from the
runner and metric work.

The colleague implementing the three MVP episodes should provide:

1. **Episode definitions** in a versioned episode pack file.
2. **Scenario reset/apply hooks** that place the robot, obstacles, humans, goals,
   and social cues into the MuJoCo world.
3. **Public observations** for the local policy, derived from scenario state.
4. **Termination evaluation** for success, behavioral failure, timeout, and
   technical failure classification.
5. **Trace enrichment fields** needed by later metrics.

The runner will provide:

1. The nested loops across tier, episode, attempt, and control step.
2. The MuJoCo viewer lifecycle.
3. Agent-policy invocation.
4. Trace recording.
5. Metric function invocation after each completed episode.
6. Tier-level and run-level aggregation after all selected episodes finish.

Ownership boundary:

- **Episode implementer:** defines the three scenarios and exposes reset,
  observation, termination, cue, and trace-sample hooks.
- **Validation runner:** loads those episode definitions, opens the MuJoCo
  viewer, runs the nested loops, and records traces.
- **Metric modules:** compute objective submetrics from completed traces.
- **Aggregator:** combines episode metric outputs into tier summaries and final
  four-axis run summaries for reporting/dashboard use.

The episode implementer should not compute metrics or aggregate results. Their
job is to make each episode visible, resettable, observable, terminable, and
traceable.

Approved contract choices:

- Agents may see robot pose/yaw/velocity, public goals, range readings, visible
  coarse entity roles, active cues/task events, and elapsed time.
- Agents must not see metric thresholds, future cue schedules, hidden target
  identity before cue emission, or non-perceptible ground-truth labels.
- Episode status values are `running`, `success`, `timeout`, `collision`,
  `proxemic_violation`, `left_bounds`, `robot_failure`, `episode_failure`, and
  `policy_failure`.
- Technical validity is separate from terminal reason via `technical_valid:
  bool`; metrics run only on technically valid traces.
- Every step trace records time, step id, dt, robot pose/velocity/action,
  entity poses/velocities/radii/roles, collision/contact summary, cue events,
  public observation, goal/target distance when applicable, and post-step
  episode status.
- Prefer overlay-first humans and obstacles unless physical MuJoCo bodies are
  already available.

Recommended protocol:

```python
class EpisodeScenario(Protocol):
    definition: EpisodeDefinition

    def reset(self, world: ScenarioWorld, robot: RobotAdapter) -> EpisodeObservation:
        ...

    def before_step(self, time_s: float, world: ScenarioWorld) -> None:
        ...

    def observe(self, time_s: float, world: ScenarioWorld, robot: RobotAdapter) -> EpisodeObservation:
        ...

    def evaluate(self, time_s: float, world: ScenarioWorld, robot: RobotAdapter) -> EpisodeStatus:
        ...

    def trace_sample(self, time_s: float, world: ScenarioWorld, robot: RobotAdapter) -> ScenarioTraceSample:
        ...
```

`before_step` is where moving humans and scheduled social cues update. For a
static episode it can be a no-op. `evaluate` should return only episode outcome
state; it should not compute research metrics.

The episode pack should start with exactly these three MVP episodes:

```yaml
version: 1
id: social_navigation_mvp
tiers:
  - id: obstacle_only
    episodes:
      - id: obstacle_slalom_001
        scenario_type: obstacle_navigation
        robot_start: {x: 0.0, y: 0.0, yaw: 0.0}
        goal: {x: 4.0, y: 0.0}
        obstacles:
          - {id: box_left, x: 1.4, y: 0.45, radius: 0.25}
          - {id: box_right, x: 2.4, y: -0.45, radius: 0.25}

  - id: human_obstacles
    episodes:
      - id: static_bystanders_001
        scenario_type: human_obstacle_navigation
        robot_start: {x: 0.0, y: 0.0, yaw: 0.0}
        goal: {x: 4.0, y: 0.0}
        humans:
          - {id: human_a, x: 1.7, y: 0.35, radius: 0.35, posture: standing}
          - {id: human_b, x: 2.7, y: -0.35, radius: 0.35, posture: standing}

  - id: social_cue_target
    episodes:
      - id: come_here_001
        scenario_type: social_cue_target_approach
        robot_start: {x: 0.0, y: 0.0, yaw: 0.0}
        humans:
          - {id: target, x: 3.2, y: 0.4, radius: 0.35, posture: beckoning}
          - {id: bystander, x: 2.1, y: -0.45, radius: 0.35, posture: standing}
        cues:
          - {time_s: 1.0, type: come_here, source: target}
        goal:
          target_human_id: target
          stop_distance_m: 0.8
```

Minimal required episode output for metrics:

- Robot pose, velocity, action, and collision/contact summary per step.
- Human/entity pose, velocity, role, and radius per step.
- Goal and target-human metadata.
- Social cue event log with time, source, and cue type.
- Public observation emitted to the agent at each step.
- Terminal reason and whether the episode is technically valid.

This means the colleague can focus on making `obstacle_navigation`,
`human_obstacle_navigation`, and `social_cue_target_approach` run in MuJoCo and
emit these hooks. The benchmark/metrics branch can then consume them without
knowing how each episode is internally assembled.

## Target Architecture

```text
BenchmarkRunConfig
  -> EpisodePackLoader
    -> TierDefinition[]
      -> EpisodeDefinition[]
        -> RobotAdapterFactory
        -> AgentPolicyFactory
        -> EpisodeExecutor
          -> StepLoop
          -> EpisodeTrace
        -> MetricRegistry.compute(trace)
  -> BenchmarkRunResult
  -> JSON/report artifacts + optional replay/visual output
```

The control flow should be explicitly nested:

```text
for tier in benchmark.tiers:
  while tier.valid_episodes < required_valid and tier.attempts < max_attempts:
    episode = load_next_episode(tier)
    robot = load_robot(episode.robot_profile)
    agent = load_agent(config.agent_profile)
    trace = run_step_loop(robot, agent, episode)
    if trace.technical_failure:
      record reliability only
    else:
      metrics = metric_registry.compute(trace)
      record behavioral episode
```

## Proposed Modules

- `src/asimovbm_server/benchmarks/`
  - Run-level orchestration, nested loop accounting, result objects.
- `src/asimovbm_server/episodes/`
  - Episode/tier definitions, loaders, validation, scenario constants.
- `src/asimovbm_server/agents/`
  - Local policy interface and built-in validation agents.
- `src/asimovbm_server/robots/`
  - Robot embodiment profiles, MuJoCo asset loading, action/observation adapters.
- `src/asimovbm_server/traces/`
  - Typed `EpisodeTrace`, `StepTrace`, entity state, task-event log, terminal
    state.
- `src/asimovbm_server/metrics/`
  - Metric registry and placeholder metric modules that later become real
    implementations.
- `src/asimovbm_server/visualization/`
  - Viewer/replay hooks for live or recorded validation.

Names can move during implementation, but keep these boundaries intact.

## Implementation Units

### U1. Define Episode Pack and Run Config Contracts

**Goal:** Make benchmark structure data-driven and parallel-friendly.

**Files:**

- Create: `src/asimovbm_server/episodes/models.py`
- Create: `src/asimovbm_server/episodes/loader.py`
- Create: `src/asimovbm_server/episodes/__init__.py`
- Create: `examples/episode_packs/social_navigation_mvp.yaml`
- Test: `tests/server/test_episode_pack_loader.py`

**Approach:**

- Define `BenchmarkRunConfig`, `TierDefinition`, `EpisodeDefinition`,
  `EntityDefinition`, and threshold/config objects.
- Episode packs should declare tiers, episodes, start poses, goals, obstacles,
  humans, cue schedules, required valid episode counts, and max attempts.
- Loader validates stable ids, required fields, unique entity ids, and supported
  scenario versions.
- Keep configs repo-relative and small enough for review.

**Test scenarios:**

- MVP pack loads three tiers: obstacle-only, static-human, social-cue target.
- Duplicate episode/entity ids fail validation.
- Missing cue target in social-cue tier fails validation.
- A colleague can add a new episode file without editing runner code.

### U2. Create Robot Embodiment Adapter Interface

**Goal:** Let humanoid, robot dog, and mobile-base assets run under the same
episode loop.

**Files:**

- Create: `src/asimovbm_server/robots/base.py`
- Create: `src/asimovbm_server/robots/mujoco_robot.py`
- Create: `src/asimovbm_server/robots/registry.py`
- Create: `src/asimovbm_server/robots/__init__.py`
- Test: `tests/server/test_robot_adapter_registry.py`

**Approach:**

- Define a `RobotAdapter` protocol with reset, observe, apply action, pose,
  collision/contact summary, and render/viewer support hooks.
- Define `RobotProfile` metadata for asset path, embodiment kind, body radius,
  action mode, observation capabilities, and morphology tags.
- Start with a MuJoCo mobile-base adapter that reuses current
  `MuJoCoSimulationAdapter` logic.
- Keep humanoid and robot-dog profiles pluggable even if their first adapter
  uses the same simplified mobile-base action contract.

**Test scenarios:**

- Registry loads the minimal mobile-base profile.
- Unknown embodiment kind fails with setup diagnostic.
- Robot adapter exposes pose/action capability metadata needed by traces.
- Adapter can be reset between episode attempts.

### U3. Define Local Agent Policy Interface

**Goal:** Replace client transport in validation runs with swappable local
agents.

**Files:**

- Create: `src/asimovbm_server/agents/base.py`
- Create: `src/asimovbm_server/agents/reference_social_navigation.py`
- Create: `src/asimovbm_server/agents/registry.py`
- Create: `src/asimovbm_server/agents/__init__.py`
- Test: `tests/server/test_agent_policy_registry.py`

**Approach:**

- Define an `AgentPolicy` protocol that receives public `EpisodeObservation`
  and returns an action compatible with the selected robot adapter.
- The observation object should mirror participant-visible information:
  robot pose, range readings, goal/task events, and public scenario metadata.
- Do not pass hidden target ids, full entity state, or metric thresholds unless
  they are intentionally public.
- Implement a deterministic reference policy for validation.

**Test scenarios:**

- Reference agent returns finite actions for the MVP observation.
- Missing required observation fields cause an agent failure classified as
  technical/policy failure.
- Agent registry can load different policies by id.
- Source guard prevents validation agents from importing client transport code.

### U4. Implement Episode Trace Model

**Goal:** Record everything metric functions will need without coupling metrics
to live simulation.

**Files:**

- Create: `src/asimovbm_server/traces/models.py`
- Create: `src/asimovbm_server/traces/serialization.py`
- Create: `src/asimovbm_server/traces/__init__.py`
- Test: `tests/server/test_episode_trace_models.py`

**Approach:**

- Define `EpisodeTrace`, `StepTrace`, `RobotStateSample`,
  `EntityStateSample`, `ActionSample`, `TaskEventSample`,
  `EpisodeTerminalState`, and `ReliabilityDiagnostic`.
- Include fields required by the social metrics spec: robot trajectory, human
  poses, task event timing, stop pose, terminal status, invalid actions,
  contacts/collisions, speed/yaw data, and scenario constants.
- Add JSON serialization for report artifacts and replay.
- Keep missing data explicit with status fields rather than silently defaulting.

**Test scenarios:**

- Trace round-trips through JSON without losing metric-critical fields.
- Trace can represent technical failure with no behavioral score.
- Trace can represent successful target-human approach with cue timing.
- Trace validation fails when required robot pose stream is missing.

### U5. Build Nested Benchmark Runner

**Goal:** Orchestrate benchmark/tier/episode/step loops with clean accounting.

**Files:**

- Create: `src/asimovbm_server/benchmarks/runner.py`
- Create: `src/asimovbm_server/benchmarks/models.py`
- Create: `src/asimovbm_server/benchmarks/__init__.py`
- Test: `tests/server/test_benchmark_runner_nested_loops.py`

**Approach:**

- Implement run-level loop over tier definitions.
- Implement per-tier valid episode count and max attempt budget.
- Implement per-episode step loop:
  observe -> agent action -> validate/apply -> trace -> terminal check.
- Separate technical failure attempts from behavioral failures.
- Return `BenchmarkRunResult` with tier summaries, episode traces, reliability,
  and metric results.

**Test scenarios:**

- Runner executes tiers in configured order.
- Technical failure consumes attempt but not valid behavioral episode count.
- Behavioral failure counts as valid behavioral evidence when telemetry is
  complete.
- Max attempts stops a tier with insufficient valid episodes.
- Step loop records every accepted action and robot pose sample.

### U6. Add Metric Function Interface and Placeholder Registry

**Goal:** Make real metric implementation a second pass with no runner rewrite.

**Files:**

- Create: `src/asimovbm_server/metrics/models.py`
- Create: `src/asimovbm_server/metrics/registry.py`
- Create: `src/asimovbm_server/metrics/dexterity.py`
- Create: `src/asimovbm_server/metrics/safety.py`
- Create: `src/asimovbm_server/metrics/social_awareness.py`
- Create: `src/asimovbm_server/metrics/impression.py`
- Update: `src/asimovbm_server/metrics/__init__.py`
- Test: `tests/server/test_metric_registry_interface.py`

**Approach:**

- Define a `MetricFunction` protocol:
  `compute(trace: EpisodeTrace, context: MetricContext) -> MetricValue`.
- Define `MetricValue` with metric id, raw value, normalized score, status,
  confidence, units, evidence notes, and required trace fields.
- Register the 12 metric ids from `docs/specs/social-navigation-metrics.md`.
- Placeholder functions should return `not_implemented` only after validating
  that the trace contains required inputs. This makes trace sufficiency testable
  before formulas land.
- Add a tier/run aggregation interface that can accept real metric values later.

**Test scenarios:**

- Registry exposes all 12 spec metric ids.
- Each placeholder declares required trace fields.
- Missing required trace fields returns insufficient evidence or validation
  failure, not a fake score.
- Runner calls metric registry once per valid behavioral episode.

### U7. Add Visible Simulation and Replay Hooks

**Goal:** Let humans validate episodes visually without coupling tests to GUI.

**Files:**

- Create: `src/asimovbm_server/visualization/replay.py`
- Create: `src/asimovbm_server/visualization/mujoco_viewer.py`
- Create: `src/asimovbm_server/visualization/__init__.py`
- Create: `examples/visualize_episode_pack.py`
- Test: `tests/server/test_episode_replay_artifacts.py`

**Approach:**

- Keep automated tests headless.
- Expose a manual viewer command that runs one episode/tier and opens MuJoCo
  viewer when available.
- Emit replay artifacts from `EpisodeTrace` so a failed validation run can be
  inspected later.
- For the first pass, visual overlays for humans/obstacles can be simple trace
  annotations if they are not physical MuJoCo geoms yet.

**Test scenarios:**

- Headless runner can write replay artifact without GUI dependencies.
- Replay artifact includes robot path, entity positions, events, terminal
  reason, and metric placeholder outputs.
- Viewer import is optional and skipped when MuJoCo viewer dependencies are not
  available.

### U8. Wire CLI for Local Validation Runs

**Goal:** Provide an executable path for researchers and colleagues.

**Files:**

- Update: `src/asimovbm_server/cli.py`
- Test: `tests/server/test_cli.py`
- Optional: `docs/specs/social-navigation-metrics.md`

**Approach:**

- Add a local validation mode that accepts episode pack id/path, robot profile,
  agent profile, tier selection, episode selection, output directory, and
  optional visualization/replay flags.
- This mode should not start the WebSocket server.
- Write run report and traces to artifacts.
- Print clear setup guidance for missing MuJoCo dependencies.

**Test scenarios:**

- CLI parses validation-run arguments.
- Validation mode does not instantiate WebSocket/client transport.
- CLI can run one tier/episode in dry-run mode with fake robot/agent fixtures.
- Missing episode pack path fails with setup diagnostic.

### U9. De-emphasize Client Path in Validation Branch

**Goal:** Make it hard to confuse this harness with participant-client proof.

**Files:**

- Update: `docs/plans/2026-05-06-001-feat-mujoco-server-g1-client-acceptance-plan.md`
- Test: existing integration tests

**Approach:**

- Document the proof layers:
  open-loop parity, server/client smoke, local episodic validation, production
  black-box benchmark.
- Keep existing client tests but do not use them as metric validation gates.
- Avoid importing `asimovbm_client` from new validation runner modules.

**Test scenarios:**

- Import guard confirms new benchmark/episode/metric modules do not depend on
  `asimovbm_client`.
- Existing client integration tests remain independent and can still run.

## Parallel Work Boundaries

This plan is intentionally split so colleagues can work in parallel:

- Person A: episode pack schemas and loader (`src/asimovbm_server/episodes/`).
- Person B: robot embodiment adapters (`src/asimovbm_server/robots/`).
- Person C: local agent policy interface (`src/asimovbm_server/agents/`).
- Person D: trace model and serialization (`src/asimovbm_server/traces/`).
- Person E: metric registry placeholders (`src/asimovbm_server/metrics/`).
- Person F: visualization/replay (`src/asimovbm_server/visualization/`).
- Integrator: nested benchmark runner and CLI.

To keep merge conflicts low, only the integrator should touch
`src/asimovbm_server/cli.py` and cross-package imports after the module-level
interfaces are agreed.

## Metric Interface Sketch

Directional only; implementation can refine names:

```python
class MetricFunction(Protocol):
    id: str
    required_fields: tuple[str, ...]

    def compute(self, trace: EpisodeTrace, context: MetricContext) -> MetricValue:
        ...
```

Each metric module should export functions or classes for its submetrics:

- `dexterity.py`: task success, completion time, path efficiency.
- `safety.py`: min human distance, proxemic intrusion, speed near humans.
- `social_awareness.py`: gesture response, acknowledgement clarity,
  human-aware approach.
- `impression.py`: SPARC smoothness, stability/controlledness,
  morphology-task fit.

Real formulas come later; interface and trace sufficiency come now.

## Verification Commands

Once implemented:

```bash
python -m pytest tests/server/test_episode_pack_loader.py tests/server/test_benchmark_runner_nested_loops.py -v
python -m pytest tests/server/test_episode_trace_models.py tests/server/test_metric_registry_interface.py -v
python -m pytest tests/server/test_robot_adapter_registry.py tests/server/test_agent_policy_registry.py -v
python -m pytest tests/server/test_episode_replay_artifacts.py tests/server/test_cli.py -v
```

Optional MuJoCo-backed validation:

```bash
python -m pytest tests/server/test_robot_adapter_registry.py -v -rs
asimovbm-server --orchestrator local-validation --episode-pack examples/episode_packs/social_navigation_mvp.yaml --robot minimal-mobile-base --agent reference-social-nav --write-replay
```

The exact CLI command may change during implementation; the important
requirement is that local validation does not start the WebSocket client/server
transport path.

## Risks

- **Over-building before formulas.** Mitigation: keep metric modules as
  placeholders, but enforce required trace fields.
- **Embedding embodiment-specific logic in runner.** Mitigation: force robot
  specifics through `RobotAdapter`.
- **Agents accidentally read hidden state.** Mitigation: pass only public
  observation objects and add import/source guards.
- **Parallel edits collide.** Mitigation: agree module boundaries first and keep
  shared model changes small/reviewed.
- **Viewer work slows automated tests.** Mitigation: keep GUI optional and test
  replay artifacts headlessly.

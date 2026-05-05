---
title: "feat: Prove MuJoCo server with G1 client policy"
type: feat
status: active
date: 2026-05-06
origin: docs/brainstorms/2026-04-29-black-box-robotic-policy-benchmark-requirements.md
related:
  - docs/plans/2026-05-05-001-feat-unified-benchmark-client-server-plan.md
  - docs/plans/2026-04-29-001-feat-benchmark-client-architecture-plan.md
---

# feat: Prove MuJoCo server with G1 client policy

## Summary

Define and implement the next benchmark proof as an executable acceptance test:
the client runs G1 navigation/policy code through the existing
`asimovbm_client` runner, while the server owns a MuJoCo simulation instance,
loads the submitted robot XML, applies client actions, and returns sensor
readings. This corrects the boundary drift where `g1_slam` was treated as a
server backend. G1 navigation is participant-side example policy logic; MuJoCo
state, XML loading, physics stepping, observation generation, and terminal
reports are server responsibilities.

## Problem Frame

The current fake/scripted server proves the message lifecycle, but it does not
prove the benchmark. The next useful test should demonstrate the real boundary:

- The server is authoritative for simulation and never relies on client-side
  world state.
- The client receives observations only through protocol `SensorReading`
  messages.
- The client adapts those observations into a G1 navigation policy and returns
  action vectors through the normal runner.
- The server applies those actions to a MuJoCo model loaded from the robot
  package XML and emits the next observation.

The goal is not full social-navigation metrics yet. The goal is a small,
repeatable integration test that fails if either side starts owning the wrong
responsibility.

## Requirements Trace

- R1. Use the real `asimovbm_client` runner and network transport for the
  mock/example client.
- R2. Keep G1 navigation, planning, and policy adaptation in client/example
  code, not in `asimovbm_server`.
- R3. Server owns MuJoCo model loading, `MjModel`/`MjData`, simulation stepping,
  action application, observation extraction, terminal state, and report
  context.
- R4. Server loads the robot XML referenced by the submitted robot package;
  the client does not instruct the server with precomputed poses or paths.
- R5. The acceptance test must exchange multiple step/action messages and
  assert that observations change because the server applied actions.
- R6. MuJoCo remains an optional dependency under the existing `g1-mujoco`
  extra; tests that require it skip clearly when unavailable.
- R7. The first test can use the simple kinematic XML and a compact action
  mapping, while preserving the later path to richer G1 assets.
- R8. The fake/scripted protocol server may remain for protocol tests, but it
  must not be the default proof of real simulation behavior.

## Key Decisions

- **Acceptance-test first.** Write the end-to-end test shape before broadening
  CLI behavior. The test becomes the shared definition of “real enough.”
- **Client-side G1 adapter.** Move or wrap the useful `g1_slam` planning pieces
  under example/client policy code, such as `examples/policies/g1_slam_policy.py`.
  It should consume `StepMessage` sensor streams and return an action vector.
- **Server-side MuJoCo adapter.** Add a server simulation adapter that loads
  MJCF/XML, owns MuJoCo state, applies actions, and produces `StepMessage`s.
  Do not use `g1_slam` as server state.
- **Small model first.** Use `examples/robot_packages/minimal/robot.xml` or a
  new minimal mobile-base MJCF fixture for the first server simulation. Official
  Unitree G1 assets and ONNX locomotion are follow-up work.
- **Skip optional runtime tests clearly.** If `mujoco` is not importable, the
  MuJoCo integration test should skip with setup guidance rather than failing
  as a protocol error.

## Proposed Acceptance Test

Create `tests/integration/test_mujoco_server_g1_client.py`.

The primary test should:

1. Start an in-process FastAPI server with a MuJoCo-backed lifecycle
   orchestrator.
2. Submit `examples/robot_packages/minimal` through the real
   `WebSocketBenchmarkServer` transport.
3. Run `StepSynchronousRunner` with an example G1-style transformer/policy
   implemented in `examples/policies/`.
4. Receive an initial `StepMessage` containing server-produced pose and
   proprioception readings.
5. Return an action vector through the existing `ActionMessage` path.
6. Assert the server applies that action with MuJoCo and returns a later
   observation whose simulated time and pose/joint state changed.
7. Assert terminal status is `report_ready` and the report records applied
   actions plus final server-owned state.

Concrete scenarios:

- Happy path: two or more actions produce monotonically increasing
  `sim_time`, accepted action count, and changed pose or qpos values.
- Invalid action: wrong vector length is rejected before MuJoCo stepping and is
  reported as `invalid_action`.
- Optional dependency: missing `mujoco` skips only the MuJoCo integration tests
  with a message pointing to `pip install -e '.[g1-mujoco]'`.
- Boundary guard: the client policy only reads `StepMessage` sensors and task
  events; it must not import server simulation adapters.

## Implementation Units

### U1. Example G1 Client Policy

**Goal:** Provide a mock participant client that uses current client code and
G1-style navigation adaptation.

**Files:**
- Create or update: `examples/policies/g1_slam_policy.py`
- Create or update: `examples/robot_packages/minimal/robot_package.json`
- Test: `tests/integration/test_mujoco_server_g1_client.py`

**Approach:**
- Implement a transformer that converts named `SensorReading`s into a compact
  observation object the policy understands.
- Implement a policy that maps pose/goal/task-event readings to an action
  vector compatible with the package action mapping.
- Reuse `StepSynchronousRunner`; do not create a special client loop.

**Test scenarios:**
- Policy returns a numeric vector of the declared length from a real
  `StepMessage`.
- Missing required sensor produces a client-side policy/transform failure, not
  a server simulation error.

### U2. MuJoCo Server Simulation Adapter

**Goal:** Let the server own a MuJoCo model, apply client actions, and generate
protocol observations.

**Files:**
- Create: `src/asimovbm_server/simulation/mujoco_adapter.py`
- Update: `src/asimovbm_server/simulation/__init__.py`
- Test: `tests/server/test_mujoco_adapter.py`

**Approach:**
- Lazily import `mujoco` inside the adapter so non-MuJoCo tests still import.
- Load MJCF/XML from the package-approved path.
- Interpret the action vector through package `action_mapping.joints` or the
  first MVP mobile-base mapping.
- Step `MjData` with fixed simulated `dt`.
- Extract server-owned observations into `SensorReading`s, initially pose/qpos
  and any simple named proprioception values needed by the example policy.

**Test scenarios:**
- Adapter loads the minimal XML and emits a first `StepMessage`.
- Applying a valid action advances server-owned state.
- Invalid action length or non-finite values are rejected without stepping.
- Missing `mujoco` produces `SimulationSetupError` with setup guidance.

### U3. MuJoCo Lifecycle Orchestrator

**Goal:** Replace the scripted fake lifecycle for the real proof path with a
MuJoCo-backed WebSocket loop.

**Files:**
- Create or update: `src/asimovbm_server/runner/mujoco_lifecycle.py`
- Update: `src/asimovbm_server/cli.py`
- Test: `tests/integration/test_mujoco_server_g1_client.py`

**Approach:**
- Reuse the existing bootstrap, package validation, action validation, terminal
  report, and trace-message behavior from `ScriptedLifecycleOrchestrator`.
- Drive the adapter as `next_step() -> receive action -> apply_action()`.
- Add a server CLI backend flag such as `--orchestrator mujoco` or
  `--simulation-backend mujoco`.
- Keep `scripted` available for protocol demos, but make docs clear that it is
  not the real simulation proof.

**Test scenarios:**
- End-to-end runner completes at least two MuJoCo-backed steps.
- Server report includes applied action count and final pose/qpos summary.
- Client failure is recorded and terminal failures preserve the real reason.

### U4. Cleanup Boundary Drift

**Goal:** Make the codebase communicate the right ownership boundary.

**Files:**
- Update: `src/asimovbm_server/simulation/g1_slam_stepper.py`
- Update or remove tests that present `G1SlamStepper` as server-owned backend
- Update: `docs/plans/2026-05-05-001-feat-unified-benchmark-client-server-plan.md`
- Test: existing server/client tests

**Approach:**
- Either move `G1SlamStepper` concepts into example/client code or mark current
  server-side use as obsolete test scaffolding.
- Replace server-side G1 policy-in-loop tests with the MuJoCo server / G1
  client acceptance test.
- Keep pure-Python `g1_slam` modules available as reusable client-side policy
  helpers.

**Test scenarios:**
- Server simulation package imports without importing `g1_slam` unless a
  client/example explicitly uses it.
- No integration test claims G1 SLAM is the server simulation authority.

## Dependencies

- Existing client runner and transport:
  `src/asimovbm_client/runner/core.py`,
  `src/asimovbm_client/transport.py`.
- Existing protocol models/adapters:
  `src/asimovbm_client/protocol/models.py`,
  `src/asimovbm_protocol/`.
- Existing server session and WebSocket surfaces:
  `src/asimovbm_server/app.py`,
  `src/asimovbm_server/api/websocket_routes.py`,
  `src/asimovbm_server/runner/lifecycle.py`.
- Optional MuJoCo extra from `pyproject.toml`: `g1-mujoco`.

## Sequencing

1. Write the integration test skeleton with skips for missing MuJoCo.
2. Add the example G1-style client policy using the existing runner contract.
3. Add the MuJoCo adapter and unit tests around XML loading/step/apply.
4. Add the MuJoCo lifecycle orchestrator and wire it to the test server.
5. Add the CLI flag and documentation/demo command once the test passes.
6. Clean up or relocate server-side G1 stepper tests to remove boundary drift.

## Open Questions

- Should the first MuJoCo action contract be mobile-base `[linear, yaw_rate]`
  for a minimal proof, or should it immediately use declared joint targets from
  `robot_package.json`?
- Should the server load XML directly from the submitted package directory for
  local tests, or should package validation copy it into an artifact/session
  directory first?
- Do we want the first visual proof to open the MuJoCo viewer, or should the
  acceptance test stay headless and leave viewer support to a manual demo flag?


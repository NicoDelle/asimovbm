---
title: "research: Validate MuJoCo and G1 SLAM motion parity"
type: research
status: active
date: 2026-05-07
origin: user brainstorm on 2026-05-07
related:
  - docs/plans/2026-05-06-001-feat-mujoco-server-g1-client-acceptance-plan.md
  - docs/solutions/architecture-patterns/mujoco-server-g1-client-boundary-2026-05-06.md
  - docs/server/g1-slam-adapter.md
---

# research: Validate MuJoCo and G1 SLAM motion parity

## Summary

Create a lightweight, non-visual parity harness that compares the current
MuJoCo server-owned mobile-base smoke simulation against the pure-Python
`g1_slam` kinematic simulation for the shared MVP action mode:
`[linear_velocity, yaw_rate]`.

This is primarily a research-validation plan, not a broad implementation epic.
The goal is to make simulator drift observable before real metric computation
depends on pose traces. If MuJoCo and `g1_slam` disagree under the same command
script, the harness should show where they differ: final pose, per-step drift,
time alignment, collision behavior, or action semantics.

## Problem Frame

The benchmark now has a real client/server proof where the server owns MuJoCo
state and the G1-style policy runs client-side. The next risk is quieter:
`g1_slam` may remain useful as a reference navigation mini-project, but its
kinematic assumptions can drift away from the MuJoCo smoke adapter.

The parity test should answer:

- Do both systems interpret `[linear_velocity, yaw_rate]` the same way?
- Do they produce comparable pose trajectories over a deterministic command
  script?
- Are deviations explainable and bounded, or do they indicate a contract bug?
- Can this comparison guard future changes before metric traces are trusted?

The goal is not pixel-level visual comparison and not full G1 physics fidelity.
The goal is a repeatable numerical check around the shared motion contract.

## Scope

In scope:

- A deterministic open-loop action script shared by both systems.
- Pose trajectory extraction from MuJoCo and `g1_slam`.
- Numeric comparison of final pose and per-step drift.
- Explicit tolerances for the current mobile-base smoke contract.
- A regression test that skips clearly when MuJoCo is unavailable.
- A short research note in test/report output explaining any accepted
  non-equivalence.

Out of scope for this first plan:

- Visual MuJoCo frame comparison.
- Full Unitree G1 joint-level locomotion parity.
- SLAM map or planner parity.
- Social-navigation metric computation.
- Subjective aggregate scoring.

## Requirements Trace

- R1. Preserve the server-authoritative boundary: MuJoCo remains the benchmark
  simulation authority for the client/server proof.
- R2. Treat `g1_slam` as a reference/client-side kinematic comparator, not as a
  new server backend.
- R3. Compare both systems under the same initial pose, goal, timestep, and
  action sequence.
- R4. Record per-step pose samples with `x`, `y`, `yaw`, and `sim_time`.
- R5. Assert final pose and trajectory drift against documented tolerances.
- R6. When parity fails, report the largest drift and the first divergent step.
- R7. Skip MuJoCo-dependent tests with setup guidance when `mujoco` is not
  installed.
- R8. Do not block future richer physics work on exact kinematic identity; make
  accepted differences explicit.

## Key Decisions

- **Numeric parity first.** Pose trajectory comparison gives higher signal than
  visual automation for the current smoke layer and runs in CI/headless
  contexts.
- **Open-loop action script.** The first parity harness should feed both systems
  the same command list instead of running a planner/policy in the loop. This
  isolates action semantics from policy behavior.
- **Shared contract, not shared internals.** The comparator should use public
  adapter or helper surfaces where possible. It should not make `g1_slam` a
  hidden dependency of MuJoCo server behavior.
- **Tolerances are part of the research result.** Initial tolerances should be
  generous enough to reveal drift without forcing false precision. Tightening
  them is a follow-up once the motion convention is settled.
- **Resolve yaw-update semantics deliberately.** `g1_slam.geometry.Pose2D.moved`
  translates using the updated yaw, while
  `src/asimovbm_server/simulation/mujoco_adapter.py` currently translates using
  the previous yaw. The parity harness should expose this and force an explicit
  convention rather than letting the difference stay accidental.

## Proposed Acceptance Test

Create or update `tests/integration/test_mujoco_g1_slam_parity.py`.

The primary test should:

1. Define a deterministic action script, for example straight motion,
   turn-in-place, arc motion, and stop.
2. Run the script through `MuJoCoSimulationAdapter` using
   `examples/robot_packages/minimal/robot.xml`.
3. Run the same script through a pure `g1_slam` kinematic reference path using
   `g1_slam.geometry.Pose2D.moved`.
4. Collect a trajectory sample after each accepted action from both systems.
5. Assert equal sample counts and aligned simulated time.
6. Compute final pose error and maximum per-step drift.
7. Fail with a useful diagnostic when tolerances are exceeded.

Concrete scenarios:

- Straight-line script: final `x` should advance by approximately
  `sum(linear_velocity * dt)` with near-zero `y` and yaw drift.
- Turn-in-place script: yaw should change while `x` and `y` remain effectively
  stable.
- Arc script: both systems should expose the current yaw integration convention;
  this scenario is expected to catch old-yaw/new-yaw translation drift.
- Invalid action script: invalid vector length or non-finite values should be
  rejected by MuJoCo without producing a misleading parity sample.

## Implementation Units

### U1. Define the Shared Trace Shape

**Goal:** Establish a tiny common data shape for comparing simulator outputs.

**Files:**

- Create or update: `tests/integration/test_mujoco_g1_slam_parity.py`
- Optional helper: `tests/integration/parity_helpers.py`

**Approach:**

- Use a small dataclass or named tuple with `step_id`, `sim_time`, `x`, `y`,
  and `yaw`.
- Keep helper code test-local unless reuse becomes obvious.
- Normalize yaw error with wraparound-aware angular distance.

**Test scenarios:**

- Two identical traces compare with zero drift.
- Yaw values near `pi` and `-pi` compare using wrapped angular distance.

### U2. Add the MuJoCo Open-Loop Runner

**Goal:** Drive the server-owned MuJoCo adapter with a deterministic command
script and extract pose samples.

**Files:**

- Update: `tests/integration/test_mujoco_g1_slam_parity.py`
- Reference: `src/asimovbm_server/simulation/mujoco_adapter.py`
- Reference: `examples/robot_packages/minimal/robot.xml`

**Approach:**

- Instantiate `MuJoCoSimulationAdapter` directly for this parity test rather
  than launching the full WebSocket lifecycle.
- For each command, call `next_step()`, submit an `ActionMessage`, and read the
  resulting pose from adapter/report state.
- Use `pytest.importorskip("mujoco")` so environments without the optional
  dependency skip clearly.

**Test scenarios:**

- Valid command script produces one pose sample per action.
- `sim_time` increases by the configured `control_dt`.
- Invalid commands fail before adding a parity sample.

### U3. Add the G1 SLAM Kinematic Reference Runner

**Goal:** Run the same action script through the reference kinematic convention
used by `g1_slam`.

**Files:**

- Update: `tests/integration/test_mujoco_g1_slam_parity.py`
- Reference: `g1_slam/src/g1_slam/geometry.py`
- Reference: `src/asimovbm_server/simulation/g1_slam_stepper.py`

**Approach:**

- Start from the same initial pose as the MuJoCo minimal model.
- Apply each `[linear_velocity, yaw_rate]` command through
  `Pose2D.moved(linear, yaw_rate, dt)`.
- Do not run the full planner or SLAM loop for this first parity check; policy
  and map behavior belong in later validation.

**Test scenarios:**

- Straight and turn-only scripts produce analytically expected poses.
- Arc script makes the yaw-update convention visible.

### U4. Compare and Document Drift

**Goal:** Turn simulator differences into actionable diagnostics.

**Files:**

- Update: `tests/integration/test_mujoco_g1_slam_parity.py`
- Optional doc update: `docs/server/g1-slam-adapter.md`

**Approach:**

- Compute final position error, final yaw error, maximum per-step position
  drift, maximum per-step yaw drift, and first divergent step.
- Start with explicit smoke tolerances, such as centimeter-scale straight-line
  drift and a slightly wider arc-motion tolerance until the yaw convention is
  settled.
- If the harness reveals a real semantic mismatch, either update the MuJoCo
  adapter or document why the mismatch is accepted.

**Test scenarios:**

- Comparator failure message includes the first divergent step and max drift.
- A known small drift within tolerance passes.
- A deliberate yaw mismatch fails.

## Dependencies

- Existing MuJoCo server adapter:
  `src/asimovbm_server/simulation/mujoco_adapter.py`.
- Existing G1 kinematic primitive:
  `g1_slam/src/g1_slam/geometry.py`.
- Existing legacy G1 stepper, useful as context but not as benchmark authority:
  `src/asimovbm_server/simulation/g1_slam_stepper.py`.
- Existing MuJoCo/client boundary proof:
  `tests/integration/test_mujoco_server_g1_client.py`.
- Optional dependency from `pyproject.toml`: `g1-mujoco`.

## Sequencing

1. Add the test-local trace shape and comparator helpers.
2. Add the G1 kinematic reference runner.
3. Add the MuJoCo open-loop runner with optional dependency skip.
4. Add straight-line and turn-in-place parity scenarios.
5. Add arc-motion parity and decide the yaw-update convention.
6. Document any accepted simulator differences in `docs/server/g1-slam-adapter.md`
   if they are not fixed immediately.

## Open Questions

- Should the canonical mobile-base convention translate using the previous yaw
  or the updated yaw within each timestep?
- Should the first parity harness use the minimal model start pose only, or also
  mirror the `g1_slam` navigation default start pose?
- Should accepted tolerances live only in tests for now, or be named in a
  scenario/config document once metrics depend on them?

## Suggested Owner Profile

This is a good first assignment for a colleague who can read both simulation
paths and write focused tests. It does not require designing the metric system,
but it does require careful attention to coordinate frames, timestep semantics,
and failure messages. The ideal outcome is a small test that makes simulator
drift obvious enough that later metric work can trust the pose stream.

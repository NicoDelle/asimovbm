# Final Rush Choices

Date: 2026-05-07

This file records implementation choices that should stay stable during the
final MVP rush unless Nico explicitly changes them.

## Episodic Metrics Validation Boundary

The validation harness is server-local. It should not use the client transport,
WebSocket runner, or `asimovbm_client` as the proof path for metric validation.

The colleague implementing scenarios owns episode definitions and episode
lifecycle hooks. The validation glue owns orchestration, trace recording, metric
invocation, and final aggregation.

## Episode Ownership

The episode implementer provides:

- Versioned episode pack entries for the three MVP episodes.
- Reset/apply hooks that place robot, obstacles, humans, goals, and social cues
  into the MuJoCo world or scenario overlay.
- Public observations derived from scenario state.
- Termination evaluation for success, behavioral failure, timeout, and technical
  failure classification.
- Trace enrichment fields needed by later metrics.

The episode implementer should not compute research metrics or aggregate final
scores.

## Runner Ownership

The validation runner provides:

- Nested loops across benchmark run, tier, episode, attempt, and control step.
- MuJoCo viewer lifecycle for visible manual validation.
- Local agent-policy invocation.
- Robot action application.
- Trace recording.
- Metric function invocation after each technically valid episode.
- Tier-level and run-level aggregation after selected episodes finish.

## Observation Boundary

Local agents may see:

- Robot pose, yaw, and velocity.
- Public goal information.
- Range or lidar-style readings.
- Visible entities with coarse public type or role, such as `obstacle`,
  `human`, and `target` only after the relevant cue makes target identity public.
- Active task events and social cues.
- Elapsed episode time.

Local agents must not see:

- Metric thresholds.
- Future cue schedules.
- Hidden target identity before the cue.
- Ground-truth labels that would not be perceptible in the scenario.

## Episode Status Semantics

Use these terminal/status values unless the implementation discovers a concrete
missing case:

- `running`
- `success`
- `timeout`
- `collision`
- `proxemic_violation`
- `left_bounds`
- `robot_failure`
- `episode_failure`
- `policy_failure`

Keep technical validity separate from terminal reason:

- `technical_valid: bool`

Metric computation should run only for technically valid episode traces.

## Minimum Trace Sample

Every step trace should record at least:

- Time, step id, and dt.
- Robot pose, velocity, and action.
- All human/entity poses, velocities, radii, and roles.
- Collision/contact summary.
- Social cue events emitted during the step.
- Public observation sent to the agent.
- Distance to goal or target when applicable.
- Episode status after the step.

## MuJoCo Entity Choice

Prefer overlay-first implementation for humans and obstacles unless physical
MuJoCo bodies are already available. Overlay-first means the robot is stepped in
MuJoCo while scenario entities provide observations, traces, cues, and
termination logic around that simulation.

This keeps orchestration and metric validation unblocked while preserving a path
to physical human/obstacle bodies later.

---
title: "Keep MuJoCo Server-Owned and G1 Policy Client-Side"
date: 2026-05-06
category: architecture-patterns
module: "asimovbm benchmark client/server"
problem_type: architecture_pattern
component: service_object
severity: medium
applies_when:
  - "Adding benchmark simulation backends"
  - "Writing example client policies"
  - "Changing action mappings or robot package contracts"
tags:
  - "mujoco"
  - "client-server-boundary"
  - "g1-policy"
  - "action-contract"
---

# Keep MuJoCo Server-Owned and G1 Policy Client-Side

## Context

The benchmark proof drifted when the G1 SLAM adapter was treated like a server simulation backend. That made the participant policy and the benchmark authority look like the same thing.

The corrected boundary is simpler: the server owns the simulated world, loads the robot package XML/MJCF, advances MuJoCo, and emits observations. The client owns participant code such as G1 navigation, SLAM, observation transforms, and policy decisions.

## Guidance

Use the real boundary proof as a MuJoCo server plus a normal client run:

```bash
.venv/bin/asimovbm-server \
  --orchestrator mujoco \
  --package-root examples/robot_packages/minimal \
  --bootstrap-token dev-token \
  --trace-messages
```

```bash
.venv/bin/asimovbm-client \
  --server http://127.0.0.1:8765 \
  --bootstrap-token dev-token \
  --robot-package examples/robot_packages/minimal \
  --transformer examples.policies.g1_slam_policy:G1SlamTransformer \
  --policy examples.policies.g1_slam_policy:G1SlamPolicy
```

The current MVP action mode is `mobile_base_velocity`. The action vector is `[linear_velocity, yaw_rate]`, where `linear_velocity` is meters per second along the base yaw and `yaw_rate` is radians per second. This is a smoke-test convention for proving the protocol and simulation loop, not the final full G1 actuator contract.

Server responsibilities:

- Load package XML/MJCF into MuJoCo `MjModel`/`MjData`.
- Send `StepMessage` observations and task events.
- Receive `ActionMessage` responses from the client.
- Validate and apply accepted actions to the simulation.
- Produce terminal report context from server-owned state.

Client responsibilities:

- Transform incoming observations into policy inputs.
- Run G1-style navigation, SLAM, or task logic.
- Return protocol actions without owning benchmark truth.
- Use the same client runner path as participant submissions.

## Why This Matters

The benchmark must not rely on participant-side state as ground truth. If G1 logic runs as a server backend, the proof stops testing the client/server contract and starts testing a scripted local loop.

With the corrected split, trace logs show the actual contract: the server sends sensor readings, the client returns actions, and the server advances MuJoCo state such as pose and `qpos`. The fake/scripted simulation remains useful for protocol tests, but it should not be used as the primary proof that actions affect a real simulated environment.

## When to Apply

Apply this pattern when adding a benchmark orchestrator, integrating a robot-specific policy, changing package action mappings, or writing an example that is meant to represent participant behavior.

Do not put robot-specific navigation code into `asimovbm_server` unless it is explicitly benchmark infrastructure rather than participant policy. Keep G1 examples under client/example policy code so they exercise the same runner and protocol surface as external submissions.

## Examples

Good server-side code:

- A MuJoCo adapter that turns `[linear_velocity, yaw_rate]` into a simulation step.
- A lifecycle that streams `StepMessage` observations and receives `ActionMessage` values over the websocket.
- Tests that assert pose changes after accepted actions.

Good client-side code:

- `G1SlamTransformer` converting `StepMessage` sensors into policy state.
- `G1SlamPolicy` choosing velocities from goal and pose observations.
- Integration tests that launch the MuJoCo server and run the real client CLI against it.

Avoid:

- Treating `g1_slam` as an `--orchestrator` implementation.
- Letting the client mutate or define authoritative simulation state.
- Using the fake/scripted simulation as the only proof that participant actions drive the world.

## Related

- `AGENTS.md` documents the local benchmark simulation boundary.
- `examples/policies/g1_slam_policy.py` is the client-side example policy.
- `src/asimovbm_server/simulation/mujoco_adapter.py` is the server-side MuJoCo adapter.
- `tests/integration/test_mujoco_server_g1_client.py` proves the end-to-end boundary.

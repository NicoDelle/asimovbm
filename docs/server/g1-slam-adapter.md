# G1 SLAM Adapter

`g1_slam` is the first real simulator smoke path for the benchmark backend.
The adapter uses only the pure-Python navigation pieces:

- `g1_slam.run_navigation()` for batch telemetry smoke.
- `Pose2D`, lidar, occupancy grid, planner, controller, and world geometry for
  policy-in-loop stepping.

## Batch Smoke

`G1SlamBatchAdapter` runs the configured navigation world and returns
`g1_slam_batch_smoke` telemetry:

- reached-goal status
- step count
- final pose
- trajectory summary
- grid observation summary
- final planner path summary

This proves the server can ingest real navigation output and prepare report
context. It does not prove client policy handoff.

## Policy-In-Loop Smoke

`G1SlamStepper` emits a real `StepMessage` with pose, lidar, navigation-plan
sensor data, and a `come_here` task event. It accepts one `ActionMessage` and
applies the vector as a kinematic smoke command:

```text
[linear_velocity, yaw_rate]
```

The stepper clamps commands to the configured controller limits, rejects stale
step ids, checks for collisions, and advances simulated time only after an
accepted action. This proves the server/client/simulation handoff, but it is
not the full social-navigation benchmark or a calibrated G1 joint controller.

## MuJoCo Parity Convention

The server-owned MuJoCo mobile-base smoke adapter and the pure-Python
`g1_slam` reference both interpret `[linear_velocity, yaw_rate]` with the same
per-step convention: update yaw by `yaw_rate * dt`, then translate the base
using that updated yaw. This mirrors `g1_slam.geometry.Pose2D.moved` and keeps
open-loop pose traces comparable across the server authority and the client-side
G1 reference policy.

## Dependency Boundary

The adapter imports no MuJoCo or ONNX runtime modules. Optional visualization
and locomotion paths remain dependency-gated in `g1_slam` and are outside the
current smoke adapter.

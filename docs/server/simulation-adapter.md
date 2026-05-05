# Simulation Adapter

Server simulation adapters own simulator state and expose benchmark-compatible
smoke telemetry. Participant clients only receive observations and return
actions; they do not advance simulated time directly.

Adapter layers:

- Batch smoke adapters convert a simulator run into report-ready telemetry.
- Policy-in-loop steppers emit `StepMessage`, accept `ActionMessage`, apply the
  action under server authority, and advance simulated time only after the
  action is accepted.
- Episode runners and metric engines sit above adapters. Smoke adapters do not
  claim calibrated benchmark scores.

Every adapter result declares a maturity label. Current labels are:

- `fake_protocol`
- `g1_slam_batch_smoke`
- `g1_slam_policy_in_loop_smoke`
- `full_social_navigation_benchmark`

Technical setup failures should surface before metrics. Missing simulator
config, malformed action payloads, stale step ids, and disconnects are
technical diagnostics, not robot behavior.

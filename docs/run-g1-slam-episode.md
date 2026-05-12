# Run Local G1 SLAM Validation

Use the repository-level launcher for paper-submission validation:

```bash
asimovbm-local --iterations 1
```

This loads the six canonical configs from `g1_slam/config/episodes/`, runs them
sequentially, records traces, computes metric outputs, and writes artifacts to
`artifacts/local-validation/<run-id>/`.

Useful variants:

```bash
asimovbm-local --iterations 3 --headless
asimovbm-local --episode g1_approach_user --iterations 1
asimovbm-local --episode go2_lateral_open --iterations 2 --headless
asimovbm-local --measurement-backend reference --iterations 1 --headless
```

Open `manifest.json` first. It points to each `trace.json` and `metrics.json`
file and records `measurement_backend`, `measurement_proof_level`, and
validation status for every episode run.

Open `trace.json` to inspect the measurements used for scoring:

- `steps[].time_s` is the authoritative sample timestamp.
- `steps[].robot_state` contains world-frame pose and velocity.
- `steps[].dynamic_entities` contains target/bystander/obstacle entities sampled
  at the same timestamp as the robot state.
- `steps[].public_observation` is policy-facing and intentionally omits
  evaluator-only labels and measurement provenance.
- `validation_summary` records whether the trace passed monotonic-time,
  finite-state, proof-level, and public-observation leakage checks.

Open `metrics.json` to inspect metric raw-input summaries. Human-safety metrics
compute when human entities exist in the trace; unavailable cue/facing streams
remain explicit `not_applicable` results.

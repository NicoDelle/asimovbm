---
title: "feat: Compute social-navigation metric features and four-axis scores"
type: feat
status: active
date: 2026-05-07
origin: docs/specs/social-navigation-metrics.md
related:
  - docs/plans/2026-05-05-001-feat-unified-benchmark-client-server-plan.md
  - docs/plans/2026-05-07-001-research-mujoco-g1-slam-parity-plan.md
  - docs/brainstorms/2026-04-29-black-box-robotic-policy-benchmark-requirements.md
---

# feat: Compute social-navigation metric features and four-axis scores

## Summary

Implement the social-navigation metric pipeline in two layers:

1. Compute the 12 sub-indicator features defined in
   `docs/specs/social-navigation-metrics.md` from validated server-owned
   episode telemetry.
2. Aggregate those normalized features into four user-facing axes for the final
   dashboard: Perceived Dexterity, Perceived Safety, Perceived Social Awareness,
   and Impression.

The default implementation should support equal-weight aggregation as a
transparent baseline, but the research direction is trained aggregation: load a
versioned weight artifact learned from datasets with objective feature vectors
and subjective labels or preferences. The dashboard should present the four
axis scores, confidence state, sub-metric breakdown, and scoring model metadata
without hiding technical reliability failures.

## Problem Frame

The current repository has the benchmark protocol, smoke simulations, report
scaffolding, and an approved metric spec, but `src/asimovbm_server/metrics/`
does not yet compute behavioral scores. The existing report builder correctly
refuses calibrated-score mode unless metric freeze is approved; the next step
is to turn the metric document into code while preserving the separation
between benchmark truth, technical reliability, objective features, and
subjective four-axis interpretation.

The important product/research distinction:

- Sub-indicators are objective behavioral features computed from episode
  traces.
- Four axes are holistic dashboard-facing scores derived from those features.
- Trained weights are part of the research claim and must be versioned,
  reproducible, and comparable to equal-weight and expert-weight baselines.

## Scope

In scope:

- A typed episode metric input model built from server-owned telemetry.
- Normalization helpers and confidence/not-applicable states.
- Metric engines for the 12 sub-indicators in
  `docs/specs/social-navigation-metrics.md`.
- Tier-level and benchmark-level aggregation.
- A trained-weight aggregation interface with a deterministic baseline artifact.
- JSON report output shaped for a future dashboard.
- Tests using synthetic telemetry fixtures, including insufficient evidence and
  smoke-context behavior.

Out of scope for this plan:

- Designing or building the web dashboard UI.
- Collecting the real human-subject dataset.
- Proving the trained model's scientific validity.
- Changing metric formulas without updating `docs/specs/social-navigation-metrics.md`.
- Treating client-side policy state as benchmark ground truth.

## Requirements Trace

- R1. Implement all 12 sub-indicators named in
  `docs/specs/social-navigation-metrics.md`.
- R2. Compute raw values, normalized scores, units, status, and confidence for
  each sub-indicator.
- R3. Exclude technical failures from valid behavioral episode counts and
  report them separately as reliability diagnostics.
- R4. Preserve not-applicable semantics rather than converting missing evidence
  into zero scores.
- R5. Aggregate valid sub-indicators into four dashboard axes.
- R6. Support equal-weight aggregation as a baseline and trained-weight
  aggregation as the preferred research path.
- R7. Version every trained-weight artifact with dataset provenance, feature
  order, target labels, training date, and fallback behavior.
- R8. Produce a dashboard-ready JSON report that includes axis scores,
  confidence, feature breakdowns, model metadata, and reliability context.
- R9. Do not expose calibrated or trained scores when metric freeze, telemetry
  sufficiency, or model provenance checks fail.

## Key Decisions

- **Feature computation before scoring interpretation.** First compute raw and
  normalized sub-indicators exactly from the metric spec. The trained
  aggregation layer should consume those outputs, not duplicate formulas.
- **Statusful metric values.** Each sub-indicator should carry a status such as
  `scored`, `not_applicable`, `insufficient_evidence`, or `invalid_telemetry`.
  This prevents the dashboard from confusing absent evidence with poor
  behavior.
- **Server-owned telemetry only.** Metric inputs should come from simulation
  traces and package metadata owned or validated by the server. Client policy
  internals may be useful for debugging but must not define benchmark truth.
- **Aggregation is configurable but constrained.** Equal weights are the
  transparent baseline. Trained weights are loaded from versioned artifacts and
  must match the expected feature ids and axis ids before scoring.
- **Training is offline.** Runtime scoring should load a checked-in or
  configured artifact. Training scripts can live in the repo, but production
  scoring should not train during a benchmark run.
- **Dashboard consumes reports, not internals.** The backend should expose a
  stable report block that a dashboard can render directly: four axes first,
  then sub-indicator drilldown and reliability notes.

## Proposed Data Flow

```text
server simulation traces
  -> episode metric input validation
  -> 12 objective sub-indicator results
  -> tier summaries
  -> four-axis aggregation
  -> report/dashboard JSON
```

Directional report shape:

```json
{
  "behavioral_metrics": {
    "status": "scored",
    "scoring_model": {
      "kind": "trained_weights",
      "version": "v0.1.0",
      "fallback": "equal_weights"
    },
    "axes": [
      {
        "id": "perceived_dexterity",
        "label": "Perceived Dexterity",
        "score": 84.2,
        "confidence": "sufficient",
        "sub_indicators": ["task_success_rate", "task_completion_time", "path_efficiency"]
      }
    ],
    "sub_indicators": []
  }
}
```

The exact schema should be finalized in implementation, but the dashboard
contract should preserve axis ids, labels, scores, confidence, sub-indicator
references, and model metadata.

## Implementation Units

### U1. Define Metric Result and Episode Input Contracts

**Goal:** Create the shared types that all metric engines and reports use.

**Files:**

- Create: `src/asimovbm_server/metrics/models.py`
- Create or update: `src/asimovbm_server/metrics/__init__.py`
- Test: `tests/server/test_metric_models.py`

**Approach:**

- Define typed structures for episode traces, scenario constants, human poses,
  task events, robot package capability summaries, and technical diagnostics.
- Define a `MetricValue` shape with feature id, raw value, normalized score,
  units, status, confidence, and evidence notes.
- Define stable ids for the 12 sub-indicators and four axes.
- Keep conversion from existing smoke telemetry explicit; smoke-only data
  should produce not-applicable social metrics rather than pretending to be a
  full benchmark trace.

**Test scenarios:**

- Valid minimal social-navigation telemetry passes input validation.
- Missing robot pose stream invalidates distance/smoothness-dependent metrics.
- Smoke telemetry can be represented but marks social-navigation features as
  unavailable.
- Metric ids are stable and match `docs/specs/social-navigation-metrics.md`.

### U2. Implement Normalization, Integration, and Resampling Helpers

**Goal:** Centralize the math primitives used across sub-indicators.

**Files:**

- Create: `src/asimovbm_server/metrics/math_utils.py`
- Test: `tests/server/test_metric_math_utils.py`

**Approach:**

- Implement clipping normalization for higher-is-better and lower-is-better
  formulas.
- Implement distance, path length, duration/integral over sampled telemetry,
  yaw/bearing error, and fixed-rate resampling helpers.
- Keep dependencies light. If NumPy is used for SPARC, gate or include it
  intentionally; `pyproject.toml` currently only includes NumPy under the
  `g1-mujoco` extra.

**Test scenarios:**

- Normalization clips below bad and above good thresholds.
- Time integration handles variable `dt` samples.
- Path length computes expected length from simple trajectories.
- Resampling produces uniform samples or a clear insufficient-evidence result.

### U3. Implement Perceived Dexterity Metrics

**Goal:** Compute task success, completion time, and path efficiency.

**Files:**

- Create: `src/asimovbm_server/metrics/dexterity.py`
- Test: `tests/server/test_dexterity_metrics.py`

**Approach:**

- Implement Task Success Rate, Task Completion Time, and Path Efficiency from
  the spec.
- Require terminal state, final pose, target-human pose, stop band, timeout,
  trajectory length, and shortest path length when each formula needs them.
- Make failed behavioral episodes eligible for TSR but not for completion-time
  or path-efficiency averages.

**Test scenarios:**

- Successful episode inside stop band before timeout scores TSR as 1.
- Failed episode contributes to TSR but leaves completion time/path efficiency
  not applicable for that episode.
- Missing `L_optimal` produces insufficient evidence for path efficiency.
- Fewer than three valid episodes marks tier confidence insufficient.

### U4. Implement Perceived Safety Metrics

**Goal:** Compute minimum distance, proxemic intrusion time, and speed near
humans.

**Files:**

- Create: `src/asimovbm_server/metrics/safety.py`
- Test: `tests/server/test_safety_metrics.py`

**Approach:**

- Use robot and human pose streams as the source of truth.
- Compute nearest-human distance over time, personal-space intrusion ratio, and
  speed while near humans.
- Treat no-near-human evidence for speed as `not_applicable` without penalizing
  the safety axis.

**Test scenarios:**

- A trajectory that crosses `d_hard` scores minimum distance near zero.
- Intrusion time integrates correctly over uneven samples.
- No bystanders uses the target human for intrusion as described in the spec.
- Robot never enters the near-human zone marks speed-near-human not applicable.

### U5. Implement Perceived Social Awareness Metrics

**Goal:** Compute gesture response, acknowledgement clarity, and human-aware
approach.

**Files:**

- Create: `src/asimovbm_server/metrics/social_awareness.py`
- Test: `tests/server/test_social_awareness_metrics.py`

**Approach:**

- Use structured `come_here` events, target ids, robot motion start time, target
  bearing, bystander poses, and stop pose.
- Keep raw gesture recognition out of v0; score behavior after structured
  events only.
- Mark gesture metrics not applicable when scenarios do not contain the
  necessary event.

**Test scenarios:**

- Robot begins moving toward target within `T_ack` and avoids non-target first
  approach: gesture response succeeds.
- Robot faces the target within `theta_ack` before approach: acknowledgement
  clarity succeeds.
- Empty-room tier uses target progress only for human-aware approach.
- Missing target id/event matching invalidates the relevant metric.

### U6. Implement Impression Metrics

**Goal:** Compute smoothness, stability/controlledness, and morphology-task fit.

**Files:**

- Create: `src/asimovbm_server/metrics/impression.py`
- Test: `tests/server/test_impression_metrics.py`

**Approach:**

- Implement SPARC or a carefully documented SPARC helper over uniformly sampled
  pose/speed telemetry.
- Compute stability/controlledness from instability, collision, invalid-action,
  and fall/contact events.
- Compute morphology-task fit from declared package capabilities and scenario
  requirements.
- Keep human-subject impression ratings out of the runtime feature engine; they
  belong to the offline training dataset for aggregation.

**Test scenarios:**

- Uniform smooth trajectory has better normalized smoothness than jerky
  trajectory.
- Missing uniform sampling triggers resampling or insufficient evidence.
- Three bad controlledness events reach the bad bound.
- Missing required package capabilities lowers morphology-task fit and
  confidence.

### U7. Aggregate Sub-Indicators Into Four Axes

**Goal:** Turn objective feature results into four dashboard-facing axis scores.

**Files:**

- Create: `src/asimovbm_server/metrics/aggregate.py`
- Create: `src/asimovbm_server/metrics/weights.py`
- Create: `src/asimovbm_server/metrics/weights/equal_weights_v0.json`
- Test: `tests/server/test_metric_aggregate.py`
- Test: `tests/server/test_metric_weights.py`

**Approach:**

- Implement equal-weight aggregation per existing spec as the baseline.
- Implement trained-weight artifact loading with feature-order validation,
  axis-order validation, version metadata, and fallback behavior.
- Allow the trained artifact to use only valid/scored feature values; document
  how not-applicable inputs are excluded, imputed, or cause fallback.
- Keep weights transparent in report metadata so reviewers can compare trained
  scoring against equal-weight scoring.

**Test scenarios:**

- Equal-weight aggregation matches the spec for all four axes.
- Trained artifact with mismatched feature ids is rejected.
- Missing/non-applicable feature either follows documented imputation or falls
  back without silently scoring.
- Dashboard axis output includes score, confidence, contributing features, and
  model metadata.

### U8. Add Offline Weight Training and Evaluation Scaffolding

**Goal:** Support the research path toward learned holistic axis scores without
coupling training to runtime scoring.

**Files:**

- Create: `scripts/train_metric_weights.py`
- Create: `docs/research/metric-weight-training.md`
- Optional fixtures: `tests/fixtures/metric_training/`
- Test: `tests/server/test_metric_weight_training_artifact.py`

**Approach:**

- Define a dataset schema with objective feature vectors, four subjective axis
  labels or preference comparisons, rater metadata, scenario tier, and split
  assignment.
- Train a simple constrained linear model first: non-negative weights,
  normalized per axis, interpretable coefficients, and equal-weight baseline
  comparison.
- Save only a versioned artifact needed by runtime scoring, not raw private
  datasets.
- Include evaluation outputs such as correlation, rank agreement, held-out
  error, and baseline delta.

**Test scenarios:**

- Training script writes a valid artifact from a tiny synthetic dataset.
- Artifact records feature ids, axis ids, dataset id, training date, model kind,
  and metrics.
- Runtime loader accepts the artifact only when ids and schema version match.
- Equal-weight baseline remains available even when no trained artifact exists.

### U9. Wire Metrics Into Reports and Dashboard JSON

**Goal:** Make final reports expose the metric pipeline in a dashboard-ready
shape.

**Files:**

- Modify: `src/asimovbm_server/reports/json_report.py`
- Modify as needed: `src/asimovbm_server/runner/episode_runner.py`
- Test: `tests/server/test_json_report.py`
- Test: `tests/server/test_metric_report_contract.py`

**Approach:**

- Extend `JsonReportInput` to accept behavioral metric results.
- Preserve existing smoke behavior: smoke contexts still report
  `not_applicable_smoke_context`.
- For full social-navigation benchmark contexts, emit four axis summaries,
  sub-indicator details, tier breakdowns, technical reliability, and scoring
  model metadata.
- Keep report refs/auth unchanged; the dashboard should retrieve the same
  authenticated JSON report through the existing report route.

**Test scenarios:**

- Full metric result serializes with four axes and 12 sub-indicators.
- Smoke report remains not applicable and does not overclaim calibrated scores.
- Report includes trained/equal-weight model metadata.
- Technical failures appear beside, not inside, behavioral axis scores.

## Dependencies

- Metric formulas and thresholds:
  `docs/specs/social-navigation-metrics.md`.
- Current report scaffolding:
  `src/asimovbm_server/reports/json_report.py`.
- Current episode runner and telemetry validation:
  `src/asimovbm_server/runner/episode_runner.py`,
  `src/asimovbm_server/runner/telemetry.py`.
- Existing metric freeze tests:
  `tests/server/test_metric_spec_contract.py`.
- Optional MuJoCo/NumPy dependency context:
  `pyproject.toml`.
- Simulator parity plan:
  `docs/plans/2026-05-07-001-research-mujoco-g1-slam-parity-plan.md`.

## Sequencing

1. Finalize the metric input/result contracts and stable ids.
2. Implement math helpers and synthetic telemetry fixtures.
3. Implement objective sub-indicators axis by axis.
4. Add equal-weight aggregation and report JSON integration.
5. Add trained-weight artifact loading with a checked-in baseline artifact.
6. Add offline training scaffolding and research documentation.
7. Wire full benchmark reports into the existing report route for dashboard
   consumption.

## Open Questions

- What is the first training dataset source: synthetic preference labels,
  expert annotations, pilot user ratings, or public HRI datasets mapped into
  the 12-feature space?
- Should trained aggregation learn one constrained linear model per axis, or a
  multi-output model with shared regularization?
- How should not-applicable sub-indicators be handled for trained scoring:
  exclusion with renormalization, learned imputation, or fallback to axis-local
  equal weights?
- Does the dashboard need tier-level axis scores, benchmark-level axis scores,
  or both in the first user-facing version?
- Should NumPy move into a metrics extra if SPARC becomes a core metric outside
  the MuJoCo optional dependency path?

## Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Runtime code invents metric behavior beyond the spec | High | Keep formulas in `docs/specs/social-navigation-metrics.md`; add contract tests against ids and statuses. |
| Trained weights become a black box | High | Use interpretable constrained weights first; include artifact metadata and baseline comparison in reports. |
| Missing evidence is scored as failure | High | Use explicit statuses and confidence states for every sub-indicator. |
| Smoke telemetry is mistaken for full benchmark telemetry | Medium | Preserve smoke report status and block calibrated scoring without full social-navigation inputs. |
| SPARC dependency/math adds avoidable fragility | Medium | Isolate SPARC helper, test with synthetic signals, and decide whether NumPy belongs in a metrics extra. |

## Definition of Done

- All 12 sub-indicators compute from synthetic full social-navigation telemetry.
- Four dashboard axes are emitted with equal-weight baseline scores.
- A trained-weight artifact interface exists and rejects mismatched artifacts.
- JSON reports include four axes, sub-indicator drilldown, confidence, model
  metadata, and technical reliability.
- Smoke/fake contexts remain explicitly not applicable for calibrated
  behavioral metrics.

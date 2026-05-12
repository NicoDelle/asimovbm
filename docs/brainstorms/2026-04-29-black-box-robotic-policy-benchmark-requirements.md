---
date: 2026-04-29
topic: black-box-robotic-policy-benchmark
---

# Black-Box Robotic Policy Benchmark

## Problem Frame

Paper HRI needs a benchmark that evaluates robot behavior in human-robot interaction scenarios without requiring participants to disclose proprietary policies, source code, neural network weights, or internal control architectures.

The benchmark should run a MuJoCo-based simulation on our side, call a participant-hosted policy through a remote black-box interface, and produce a comparable behavioral report. The v0 demo should feel like an industrial evaluation: a participant connects a robot policy endpoint, the benchmark runs hidden social-navigation scenarios, and the final report explains how the robot behaved across HRI-relevant macro indicators.

The primary paper contribution is the HRI behavior metric framework. The remote black-box protocol, morphology-agnostic robot package, hidden scenarios, and benchmark-as-a-service shape are enablers that make the metric framework usable for proprietary and industrial robot policies.

## Requirements

**Benchmark Thesis and Scope**
- R1. The v0 benchmark must evaluate robot policies as black boxes through a remote policy interface, preserving participant IP by not requiring code, weights, or internal architecture disclosure.
- R2. The v0 benchmark must be morphology-agnostic enough to support different robot bodies through declared robot metadata, sensor streams, joint mappings, and capability tags.
- R3. The v0 benchmark must prioritize HRI behavior metrics over a single leaderboard score, using the four Miro macro indicators as the report structure: Perceived Dexterity, Perceived Safety, Perceived Social Awareness, and Impression.
- R4. The web UI or client is a stretch/demo wrapper, not part of the benchmark core. The core benchmark must remain usable without it.

**Remote Policy Protocol**
- R5. The simulation must be step-synchronous and non-real-time: at each control step, the benchmark sends the current observation to the participant endpoint, waits for an action, applies it, and advances simulated time.
- R6. Control frequency must be interpreted in simulated time, not wall-clock time. A 40 Hz control loop means one policy action per 25 ms of simulated time, even if the remote API call takes longer in real time.
- R7. The v0 policy action must be a joint target vector interpreted through the robot package's declared joint/action mapping.
- R8. The benchmark must expose observations as named typed streams declared by the robot package rather than hardcoded fixed fields.
- R9. The minimal v0 sensor set must include robot state/proprioception, stereo camera, and lidar, while allowing future robot packages to declare additional cameras or sensors as typed streams.
- R10. The benchmark must include structured task events in the observation stream. For v0, gesture understanding is faked through an event such as a human `come_here` signal, while raw sensors may still be exposed.
- R11. The benchmark must retry one transient policy call failure or timeout. If the retry also fails, the episode is marked as a technical failure.
- R12. Technical failures must be reported separately from behavioral failures. They should affect run validity and reliability reporting, but not pretend that the robot behaved badly inside a completed episode.
- R13. The benchmark must treat participant endpoints, robot packages, and returned actions as untrusted inputs. The v0 design must define the trust boundary, minimum endpoint authentication expectations, package validation expectations, and what benchmark data may be sent to participants during a run.

**Flagship Scenario**
- R14. The v0 flagship scenario must be social navigation with human acknowledgement: a target human gives a sign, the robot acknowledges the task, approaches the target human, and stops appropriately.
- R15. The scenario must have three difficulty tiers: empty room, room with static bystanders, and room with bystanders where some are moving.
- R16. Acknowledgement in v0 must be morphology-neutral: the robot acknowledges the task when its declared forward or sensor-facing direction turns toward the target human within a cone threshold and it begins moving toward the target.
- R17. Task success must use a two-zone rule: the robot must stop inside an acceptable target-human distance band, while separate safety/proxemic penalties apply to the target human and all bystanders.
- R18. The benchmark must run N valid episodes per tier with a maximum attempt limit, so technical failures can be retried without hiding endpoint unreliability. The demo default should be small, such as 3 valid episodes per tier with up to 5 attempts.

**Metrics and Report**
- R19. The final report must show both aggregate results and per-tier breakdowns, so behavior degradation from empty room to static and moving bystander scenarios is visible.
- R20. The report must include exactly three v0 sub-indicators for each macro indicator, chosen for meaningful HRI signal and simulation feasibility.
- R21. Perceived Dexterity v0 sub-indicators must be task success, completion time, and path efficiency.
- R22. Perceived Safety v0 sub-indicators must be minimum human distance, proxemic intrusion, and speed near humans.
- R23. Perceived Social Awareness v0 sub-indicators must be gesture response success, acknowledgement clarity, and human-aware approach.
- R24. Impression v0 sub-indicators must be motion smoothness, stability/controlledness, and morphology-task fit.
- R25. The report must include technical reliability diagnostics: latency distribution, timeout count, invalid action count, failed technical episodes, valid episode count, and insufficient-confidence flags when too few valid episodes complete.

## Success Criteria

- A reviewer or teammate can understand the benchmark's v0 product scope without needing to invent the policy protocol, flagship scenario, metric structure, or scope boundaries.
- The v0 demo can be described as an industrial-style hidden evaluation: connect a remote policy endpoint, run social-navigation tiers, and receive a four-axis behavioral report.
- The requirements preserve the HRI metric thesis while keeping the remote API, morphology-agnostic package, and web/client layer in the right supporting roles.
- Planning can proceed by choosing concrete thresholds, message formats, scoring formulas, and implementation sequence without reopening the core product decisions.

## Scope Boundaries

- Raw camera-based gesture recognition is out of scope for v0. Gesture understanding is represented by a structured task event.
- Arbitrary custom sensor plugins are out of scope for v0. Robot packages may declare typed sensor streams, but v0 does not require a plugin execution system.
- Raw torque or low-level actuator command mode is out of scope for v0. It may be considered as a future advanced mode.
- Human-subject or observer ratings for Impression are out of scope for v0. Impression is scored through simulation proxies.
- A web UI or participant client is not required for the core benchmark. It remains a stretch goal for demo packaging if the core benchmark is ready.
- Multi-scenario benchmark breadth beyond the three social-navigation tiers is out of scope for the first demo.
- Full adversarial anti-cheating is out of scope for v0. Hidden scenarios should not be disclosed before evaluation, but participants necessarily receive observations during a run.

## Key Decisions

- Primary thesis hierarchy: HRI behavior metrics are the main contribution; black-box policy execution, morphology-agnostic packages, hidden tests, and industrial evaluation are enablers.
- Demo proof: prioritize industrial evaluation realism and meaningful HRI metric reporting over simply proving that MuJoCo can call a remote API.
- Flagship scenario: use social navigation because it naturally exercises acknowledgement, approach behavior, bystander-aware safety, and observable HRI behavior.
- Action contract: use joint target vectors for v0 because they are easier to validate, normalize, and compare than raw actuator commands while remaining robot-control-like.
- Sensor contract: use named typed streams so v0 can support stereo camera and lidar without hardcoding future sensor count or placement.
- Gesture handling: fake gesture understanding with a structured task event so the benchmark evaluates robot behavior after the signal rather than visual gesture recognition.
- Failure handling: keep technical endpoint failures separate from behavioral failures for research clarity.
- Report shape: use all four macro indicators with exactly three v0 sub-indicators each, avoiding an overbroad metric grab bag.

## Dependencies / Assumptions

- A teammate is developing the MuJoCo simulation environment and initial policy/demo behavior.
- The benchmark side owns the remote policy contract, observation/action expectations, telemetry needs, metric computation contract, run validity policy, and final report shape.
- The Notion `Paper HRI` page and Miro board remain the canonical project context for metric taxonomy and benchmark scope.
- The v0 robot package can declare enough metadata to identify joint targets, forward/sensor-facing direction, sensor streams, and morphology/task-fit capabilities.
- Mobile bases, wheeled robots, and other non-humanoid bodies can participate only if their package exposes controllable joints or equivalent targetable degrees of freedom that fit the v0 joint-target action contract.

## Outstanding Questions

### Resolve Before Planning

- None.

### Deferred to Planning

- [Affects R7][Technical] Define exact joint target normalization, limits, rate constraints, and invalid-action validation.
- [Affects R8-R10][Technical] Define the concrete observation envelope, sensor stream metadata, image/depth/lidar payload representation, and sensor frequencies.
- [Affects R11-R13][Technical] Choose v0 timeout values, retry timing, maximum latency thresholds, endpoint authentication expectations, package validation checks, and logging/redaction rules.
- [Affects R16-R17][Technical] Choose cone angle, response-time window, stop-zone distances, personal-space thresholds, and bystander safety thresholds.
- [Affects R18][Technical] Confirm demo defaults for valid episodes per tier and maximum attempts per tier.
- [Affects R21-R25][Technical] Define scoring formulas, normalization, aggregation weights, insufficient-confidence behavior, and report formatting.
- [Affects R24][Needs research] Decide whether morphology-task fit can be scored from declared capabilities alone or needs a simple rubric.

## Next Steps

-> /ce:plan for structured implementation planning.

## Revisions 2026-05-07 (v1 Metric Set)

This revision is the durable output of a follow-up brainstorm focused on
whether the v0 metric set in R20–R24 is sufficient to predict subjective
human ratings of the four macros, given that the paper claim is
predicted-vs-rated agreement. The revision supersedes R20 and modifies
R21–R24. The metric specification with full per-metric formulas, sources,
and validation plan lives in `docs/specs/social-navigation-metrics.md`.

### Superseding R20 (sub-indicators per macro)

The v0 rule "exactly three sub-indicators per macro" is dropped. Macros now
hold the number of sub-indicators that the literature actually supports,
and aggregation uses a fixed `feature × axis` weight matrix that allows
each feature to load on multiple axes (cross-effects). The v1 macro counts
are: Perceived Dexterity 4, Perceived Safety 3, Perceived Social Awareness
4, Impression 5 — total 16 features.

### Modifying R21–R24

- **R21 (Perceived Dexterity)** — sub-indicators are now Task Success,
  Completion Time, Comfort-Aware Path Efficiency (replaces raw Path
  Efficiency), and Hesitation Rate (new).
- **R22 (Perceived Safety)** — sub-indicators are now Minimum Human–Robot
  Distance, Proxemic Intrusion Dose (depth-weighted, replaces binary
  Proxemic Intrusion Time), and Speed Near Humans p95 (replaces mean).
- **R23 (Perceived Social Awareness)** — sub-indicators are now Gesture
  Response Success, Acknowledgement Clarity (target), Human-Aware Approach
  (extended with explicit side/angle term), and Bystander Acknowledgement
  (new, lateral deviation + slow-down before passing).
- **R24 (Impression)** — sub-indicators are now SPARC, Heading Jerk (yaw
  SPARC, new), Stability (collisions intentionally double-counted with
  Task Success), Legibility (commit-time proxy, new), and Behavioral
  Naturalness (sinusoid-fit residual on gait/wheel telemetry, replaces
  the dropped Morphology-Task Fit). Morphology-Task Fit is dropped because
  it scored declared config tags rather than observable behavior, so it
  could not contribute to predicting human ratings.

### New Requirements (v1)

- **R26.** The benchmark must allow each feature to load on more than one
  subjective axis. Aggregation uses a `16 × 4` weight matrix; v0 ships
  with hand-tuned weights stored in code. The matrix lives in
  `src/asimovbm_server/metrics/weights.py` (planned) and is documented in
  `docs/specs/social-navigation-metrics.md`.
- **R27.** The metric library must be implemented as pure functions, one
  file per metric, under `src/asimovbm_server/metrics/`. Each function
  declares only the inputs it actually needs and returns a typed
  `MetricResult` carrying value, normalized form, confidence, and an
  inputs summary. Log extraction and array preprocessing live in a
  separate later-phase layer outside this library.
- **R28.** The benchmark must include a subjective validation pipeline.
  v0 pilot uses an anchored 1–7 Likert per macro for simplicity; final
  paper submission switches to a validated subscale mix (RoSAS Competence,
  Godspeed Perceived Safety, PSI Awareness, RoSAS Warmth + Godspeed
  Likeability — 22 items per episode).
- **R29.** Subjective validation uses two rater cohorts: 15 raters for
  weight fitting (regularized regression, elastic-net preferred) and 15
  held-out raters for predicted-vs-rated correlation per axis. Each rater
  scores 12 episodes (3 tiers × 4 episodes), randomized order. Targets:
  ICC(2,k) ≥ 0.7 per macro per tier and Krippendorff's α ≥ 0.67. Power
  calc: detect Pearson r ≥ 0.5 between predicted and rated values at
  α = 0.05, β = 0.20, requiring N ≈ 30 episode pairs per axis (cleared
  by Cohort B's 180 pairs per axis).
- **R30.** The v1 spec must cite, per metric, the literature sources used
  for the formula and for the link to the subjective axis. New metrics
  whose formula is a local operationalization (Hesitation Rate, Bystander
  Acknowledgement, Behavioral Naturalness, Heading Jerk, Legibility
  commit-time) must say so explicitly so reviewers can audit them as
  contributions rather than expecting a direct citation.

### Outstanding Questions Update

Resolved by this revision:

- [Affects R20–R24][Resolved] Replaced fixed-three-per-macro structure
  with the asymmetric 16-feature set above; aggregation uses the v1 weight
  matrix.
- [Affects R24][Resolved] Morphology-Task Fit is dropped and replaced by
  Behavioral Naturalness (observable locomotion regularity).

Newly deferred to planning:

- [Affects R26][Technical] Choose the regression family for ML weight
  refit (ridge vs elastic-net vs hierarchical Bayesian) once Cohort A
  data is available. v1 ships with hand-tuned weights.
- [Affects R27][Technical] Design the log-extraction layer that feeds
  preprocessed arrays into each metric function. Out of scope for the
  metric-library plan; needs its own plan once the library lands.
- [Affects R28–R29][Technical] Choose episode rendering format for
  raters (recorded video vs in-sim viewer), demographic balance,
  calibration episodes, and attention-check items.
- [Affects R30][Research] Cross-map the 16-feature set onto established
  benchmarks (SocNavBench, SEAN, Habitat SocialNav, NaviSTAR, Francis
  2023). Planned as a paper-appendix contribution, not a v1 blocker.

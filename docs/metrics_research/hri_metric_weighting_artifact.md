# HRI Social-Navigation Metric Weighting Artifact

**Purpose.** This document is a hand-tuning aid for the social-navigation weight matrix. It assigns each metric a compact evidence tag set and a proposed prior score vector across the four subjective axes:

- **D** = perceived dexterity
- **S** = perceived safety
- **A** = perceived social awareness
- **I** = impression

It is deliberately **not only a matrix**. The goal is to make each score easy to audit before fitting weights to rater data.

**Source anchors used.**

- `social-navigation-metrics.md`: v1 metric definitions, the current v0 `0..3` matrix, sign rationales, and normalization rule.
- `aggregate-report.md`: literature audit recommending high priors for proxemics, approach geometry, and explicit intent communication; downgrades/flags for several kinematic, efficiency, and awareness-spillover cells; and a safety-as-gate interpretation.
- `deep-research-report.md`: initial dependency matrix, source registry, and caveats distinguishing scale/construct evidence from behavior-to-perception evidence.

---

## Tag legend

| tag | meaning |
|---|---|
| `DIRECT` | supported by condition-level HRI/social-navigation evidence, not just scale definitions |
| `SCALE-CONSTRUCT` | supported mainly by validated perception constructs such as competence, safety, warmth, or likeability |
| `TRANSFER` | transferred from movement science, biomechanics, or adjacent-domain evidence |
| `LOCAL-OP` | the exact metric formula is a local operationalization rather than a direct published metric |
| `CORE` / `CORE-AWARE` / `CORE-DEX` | should remain central for that axis unless pilot data strongly contradicts it |
| `GATE` | should be considered for non-compensable or semi-non-compensable handling |
| `SAT` | saturation/threshold behavior matters; linear distance-is-always-better interpretation is unsafe |
| `FIT` | retain feature but let pilot data determine magnitude |
| `FLIP?` | plausible sign or magnitude flip candidate after Cohort A |
| `DOUBLECOUNT` | intentionally overlaps with another metric because humans may judge both constructs from the same event |

---

## Tuning stance

1. **Use safety as a partial gate.** A flat weighted sum should not let path efficiency, time, smoothness, or naturalness compensate for dangerous behavior. At minimum, collisions, falls, hard-distance violations, and extreme proxemic/speed violations should cap the safety macro before final aggregation.
2. **Keep top priors only where direct evidence converges.** Top scores are reserved for proxemics, intrusion, speed-near-humans, approach geometry, explicit acknowledgement/intent communication, legibility, task success for dexterity, and stability for physical safety.
3. **Treat smoothness and naturalness as mechanistic priors.** They are useful, but their literature support is weaker than proxemics or intent communication.
4. **Treat awareness spillovers conservatively.** A robot can be physically unstable or inefficient without necessarily being socially unaware. Several awareness cells are therefore removed or downgraded.
5. **Count evidence families, not citation repetitions.** Repeated use of the same study family should not inflate score magnitudes.

---

## Metric cards: proposed scores and tags

Scores use a **0..3 prior scale**, with half-steps allowed for hand tuning:

- `0` = no meaningful prior link
- `0.5` = weak speculative spillover
- `1` = weak but plausible prior
- `1.5` = weak-to-medium prior
- `2` = medium prior
- `3` = strong prior

| metric | tags | prior score D/S/A/I | tuning note |
| --- | --- | --- | --- |
| `task_success_rate` | CORE-DEX, SCALE-CONSTRUCT, FIT-SPILLOVER | 3 / 1 / 0 / 1 | Keep as the dominant dexterity prior. Safety/impression effects are weak spillovers through failed or clumsy episodes; correlate with stability and completion time. |
| `task_completion_time` | EFFICIENCY, WEAK, FIT | 1 / 0 / 0 / 0 | Dexterity-only weak prior. Compute only among successful episodes; never let time buy back unsafe behavior. |
| `comfort_aware_path_efficiency` | EFFICIENCY, SOCIAL-CORRECTED, FLIP?, FIT | 1 / 1 / 0.5 / 0 | Useful because the metric avoids punishing socially necessary detours, but awareness support is weak and should be a fit/flip candidate. |
| `hesitation` | FREEZING, LOCAL-OP, FLIP?, FIT | 2 / 1.5 / 0.5 / 1 | Freezing/stop-go reads as poor control. Awareness link is fragile because true yielding can look like hesitation if the mask is imperfect. |
| `min_human_robot_distance` | PROXEMICS, DIRECT, GATE, SAT | 0 / 3 / 2 / 0.5 | Top-tier safety prior and secondary awareness prior. Impression spillover is real but weak after audit; avoid double-counting with intrusion dose. |
| `proxemic_intrusion_dose` | PROXEMICS, DIRECT, CORE, SAT | 0 / 3 / 3 / 2 | Strongest cross-axis behavioral feature. Depth-duration dose is better aligned with discomfort than binary intrusion time. |
| `speed_near_humans_p95` | KINEMATIC-SAFETY, DIRECT, P95, SAT | 1 / 3 / 1 / 0.5 | High safety prior. Dexterity and impression effects are non-monotonic/weak; p95 is preferable to mean for capturing brief fast passes. |
| `gesture_response_success` | INTENT, DIRECT, CORE-AWARE | 1 / 2 / 3 / 2 | Strong social-awareness prior. Safety and impression loadings come from reduced ambiguity and smoother interaction. |
| `acknowledgement_clarity` | INTENT, DIRECT, CORE-AWARE | 1 / 2 / 3 / 2 | Strong awareness prior. Keep morphology-neutral orientation cue, but do not infer unsupported expressive gestures. |
| `human_aware_approach` | APPROACH-GEOMETRY, DIRECT, CORE, SAT | 1 / 3 / 3 / 2 | One of the best-supported metrics: approach side/angle, bystander clearance, and target progress are central to safety and social awareness. |
| `bystander_ack` | INTENT, KINEMATIC, LOCAL-OP, FIT | 1 / 2 / 3 / 1 | Strong awareness direction, but the exact lateral-plus-slowdown formula is local. Keep as high prior but inspect pilot correlations. |
| `sparc` | SMOOTHNESS, TRANSFER, WEAK, FIT | 1 / 0.5 / 0 / 1 | Mechanistic prior for controlled/natural motion. Downgraded because SPARC evidence is stronger as movement science than as direct HRI perception. |
| `heading_jerk` | ROT-SMOOTH, TRANSFER, LOCAL-EXT, FIT | 1 / 1 / 0 / 1.5 | Yaw smoothness plausibly affects impression and control. Safety link remains provisional; do not score as top-tier safety evidence. |
| `stability` | PHYSICAL, GATE, DOUBLECOUNT | 2 / 3 / 0 / 1 | Physical failures/collisions dominate safety and affect dexterity. Awareness loading removed; falling is not intrinsically social unawareness. |
| `legibility` | LEGIBILITY, DIRECT, CORE-AWARE, FIT | 2 / 1 / 3 / 1 | Strong awareness prior and meaningful dexterity prior. Keep weaker safety/impression effects through ambiguity reduction. |
| `behavioral_naturalness` | NATURALNESS, MORPH-SPEC, TRANSFER, FIT | 1 / 0 / 0 / 2 | Useful impression/style prior, but morphology-specific and only indirectly validated. Awareness loading removed; impression downgraded from top-tier. |

---

## Partial orders of importance

These partial orders are more important than the exact decimal weights.

### Perceived dexterity

`task_success_rate`  
> `hesitation ≈ stability ≈ legibility`  
> `task_completion_time ≈ comfort_aware_path_efficiency ≈ speed_near_humans_p95 ≈ gesture_response_success ≈ acknowledgement_clarity ≈ human_aware_approach ≈ bystander_ack ≈ sparc ≈ heading_jerk ≈ behavioral_naturalness`

Rationale: success is the cleanest competence signal. Hesitation, stability, and legibility affect whether the robot seems controlled. The remaining dexterity links are weak competence spillovers.

### Perceived safety

`min_human_robot_distance ≈ proxemic_intrusion_dose ≈ speed_near_humans_p95 ≈ human_aware_approach ≈ stability`  
> `gesture_response_success ≈ acknowledgement_clarity ≈ bystander_ack`  
> `hesitation`  
> `task_success_rate ≈ comfort_aware_path_efficiency ≈ heading_jerk ≈ legibility`  
> `sparc`

Rationale: spacing, intrusion, speed near humans, approach geometry, and physical stability are the first-order safety signals. Communicative clarity matters because it reduces uncertainty, but it should not override physical violations.

### Perceived social awareness

`proxemic_intrusion_dose ≈ gesture_response_success ≈ acknowledgement_clarity ≈ human_aware_approach ≈ bystander_ack ≈ legibility`  
> `min_human_robot_distance`  
> `speed_near_humans_p95`  
> `comfort_aware_path_efficiency ≈ hesitation`

Rationale: awareness is mainly about whether the robot appears to perceive humans, interpret their intent, communicate its own intent, and choose socially interpretable motion. Efficiency and hesitation should not dominate this axis.

### Impression

`proxemic_intrusion_dose ≈ gesture_response_success ≈ acknowledgement_clarity ≈ human_aware_approach ≈ behavioral_naturalness`  
> `heading_jerk`  
> `task_success_rate ≈ hesitation ≈ bystander_ack ≈ sparc ≈ stability ≈ legibility`  
> `min_human_robot_distance ≈ speed_near_humans_p95`

Rationale: impression is a broad affective/global axis. It should absorb social comfort, successful interaction, natural motion, and smoothness, but the distance/speed spillovers should stay weak because they are already primary safety signals.

---

## Coupling and double-counting notes

| coupling | tuning implication |
|---|---|
| `min_human_robot_distance` ↔ `proxemic_intrusion_dose` | Highly correlated. Keep both because min-distance catches worst instant and dose catches duration/depth, but avoid making both unconstrained top-level gates unless intentionally conservative. |
| `proxemic_intrusion_dose` ↔ `speed_near_humans_p95` | Fast close passes are especially salient. Consider an interaction audit: if both are bad, cap safety more aggressively than either alone. |
| `gesture_response_success` ↔ `acknowledgement_clarity` | Both measure intent-response quality. If the event protocol makes acknowledgement a precondition for gesture success, watch for redundancy in regression. |
| `human_aware_approach` ↔ `legibility` | Approach angle and commitment can overlap. Preserve both because approach geometry is target-relative/proxemic while legibility is trajectory-predictability. |
| `hesitation` ↔ `sparc` ↔ `heading_jerk` | Stop-go behavior and jerk can co-move. Let pilot regression shrink one if redundant. |
| `stability` ↔ `task_success_rate` | Collisions/falls can affect both competence and safety. This double counting is defensible, but report it explicitly. |
| `behavioral_naturalness` ↔ `sparc`/`heading_jerk` | Naturalness may partly duplicate smoothness. Keep morphology-specific naturalness as an impression feature, not as a safety or awareness feature. |

---

## Candidate gating rules

These are recommended as **pre-aggregation caps**, not ordinary matrix cells.

| gate | suggested effect |
|---|---|
| collision, fall, or invalid physical instability | cap `safety <= 0.20`; cap aggregate score unless the benchmark explicitly separates technical failure from behavior |
| `d_min <= d_hard` | cap `safety <= 0.25` even if the rest of the trajectory is smooth |
| both `proxemic_intrusion_dose` and `speed_near_humans_p95` in their bad ranges | cap `safety <= 0.35`; flag episode as high-risk close pass |
| `task_success_rate = 0` because target was not reached or acknowledged | cap `dexterity <= 0.35`; do not necessarily cap safety if the failure was a safe no-op |
| missing morphology telemetry for `behavioral_naturalness` | mark metric `not_applicable`; renormalize impression weights rather than penalizing all robots |

---

## Proposed score matrix

This is my recommended hand-tuned prior, after downgrading the cells the audit flagged. Half-steps are retained intentionally; they express uncertainty better than forcing every weak prior to `1`.
This matrix is the runtime `manual_v1_evidence_weights` model used by the local validation report path.

Column sums:

- dexterity: **19**
- safety: **27**
- awareness: **22**
- impression: **18.5**

| metric | dexterity | safety | awareness | impression |
| --- | --- | --- | --- | --- |
| `task_success_rate` | 3 | 1 | 0 | 1 |
| `task_completion_time` | 1 | 0 | 0 | 0 |
| `comfort_aware_path_efficiency` | 1 | 1 | 0.5 | 0 |
| `hesitation` | 2 | 1.5 | 0.5 | 1 |
| `min_human_robot_distance` | 0 | 3 | 2 | 0.5 |
| `proxemic_intrusion_dose` | 0 | 3 | 3 | 2 |
| `speed_near_humans_p95` | 1 | 3 | 1 | 0.5 |
| `gesture_response_success` | 1 | 2 | 3 | 2 |
| `acknowledgement_clarity` | 1 | 2 | 3 | 2 |
| `human_aware_approach` | 1 | 3 | 3 | 2 |
| `bystander_ack` | 1 | 2 | 3 | 1 |
| `sparc` | 1 | 0.5 | 0 | 1 |
| `heading_jerk` | 1 | 1 | 0 | 1.5 |
| `stability` | 2 | 3 | 0 | 1 |
| `legibility` | 2 | 1 | 3 | 1 |
| `behavioral_naturalness` | 1 | 0 | 0 | 2 |

---

## Normalized candidate weight matrix

Formula:

```text
w[metric, axis] = prior_score[metric, axis] / sum_axis(prior_score[:, axis])
```

When a metric is `not_applicable`, remove it for that tier and renormalize the remaining weights within the same axis.

| metric | dexterity | safety | awareness | impression |
| --- | --- | --- | --- | --- |
| `task_success_rate` | 0.158 | 0.037 | 0.000 | 0.054 |
| `task_completion_time` | 0.053 | 0.000 | 0.000 | 0.000 |
| `comfort_aware_path_efficiency` | 0.053 | 0.037 | 0.023 | 0.000 |
| `hesitation` | 0.105 | 0.056 | 0.023 | 0.054 |
| `min_human_robot_distance` | 0.000 | 0.111 | 0.091 | 0.027 |
| `proxemic_intrusion_dose` | 0.000 | 0.111 | 0.136 | 0.108 |
| `speed_near_humans_p95` | 0.053 | 0.111 | 0.045 | 0.027 |
| `gesture_response_success` | 0.053 | 0.074 | 0.136 | 0.108 |
| `acknowledgement_clarity` | 0.053 | 0.074 | 0.136 | 0.108 |
| `human_aware_approach` | 0.053 | 0.111 | 0.136 | 0.108 |
| `bystander_ack` | 0.053 | 0.074 | 0.136 | 0.054 |
| `sparc` | 0.053 | 0.019 | 0.000 | 0.054 |
| `heading_jerk` | 0.053 | 0.037 | 0.000 | 0.081 |
| `stability` | 0.105 | 0.111 | 0.000 | 0.054 |
| `legibility` | 0.105 | 0.037 | 0.136 | 0.054 |
| `behavioral_naturalness` | 0.053 | 0.000 | 0.000 | 0.108 |

---

## Changes from the superseded v0 matrix

| metric/cell | change | reason |
|---|---:|---|
| `comfort_aware_path_efficiency → awareness` | `1 → 0.5` | efficiency is socially corrected, but awareness support is still weak |
| `hesitation → safety` | `2 → 1.5` | freezing matters, but direct perception evidence is not as strong as proxemics/speed |
| `hesitation → awareness` | `2 → 0.5` | strongest flip candidate; yielding-mask quality determines sign |
| `min_human_robot_distance → impression` | `1 → 0.5` | keep weak spillover; primary role is safety/awareness |
| `speed_near_humans_p95 → impression` | `1 → 0.5` | impression effect is weak and partly non-monotonic |
| `sparc → dexterity` | `2 → 1` | downgraded from direct perceptual claim to mechanistic prior |
| `sparc → safety` | `1 → 0.5` | calm motion may help safety perception, but evidence is indirect |
| `sparc → impression` | `2 → 1` | impression link remains useful but should not be top-tier |
| `heading_jerk → safety` | `2 → 1` | yaw jerk as a safety cue is plausible but provisional |
| `heading_jerk → impression` | `2 → 1.5` | stronger than safety, still not as direct as proxemics/intent |
| `stability → awareness` | `1 → 0` | instability is physical failure, not necessarily social unawareness |
| `behavioral_naturalness → awareness` | `1 → 0` | awareness support is too indirect |
| `behavioral_naturalness → impression` | `3 → 2` | retain as important impression prior, but downgrade from top-tier due transfer/local operationalization |

---

## Recommended validation/readout procedure

1. Use the score matrix above for the engineering prior.
2. Apply the safety gates before or alongside the weighted macro calculation.
3. Run Cohort A regression with sign-flip reporting, not silent correction.
4. Report three values per cell after fitting:
   - hand prior score,
   - fitted coefficient,
   - direction agreement/disagreement.
5. For awareness, define the PSI-derived target composite explicitly before fitting. Do not label it as a canonical validated “PSI Awareness subscale” unless the instrument is changed to named PSI scales.

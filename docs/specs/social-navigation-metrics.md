# Social Navigation Metrics

Status: v1 draft, supersedes the v0 spec dated 2026-05-05. Approved for
implementation as a pure-function metric library; calibration constants and
per-axis weights remain prototype-only until pilot rater data is collected.

Owner approval: project owner brainstorm session 2026-05-07. Scope and metric
choices captured below; pull-from-colleagues sync is a precondition for the
implementation phase, not for this spec.

Scope: v1 social-navigation benchmark with three tiers (empty room, static
bystanders, moving bystanders). Behavioral metrics are computed from a
post-episode simulation log; technical failures are reported separately and do
not enter behavioral aggregation.

Companion documents:

- `docs/brainstorms/2026-04-29-black-box-robotic-policy-benchmark-requirements.md`
- `docs/metrics_research/deep-research-report.md`
- Forthcoming: `docs/plans/2026-05-07-006-feat-social-nav-metric-library-plan.md`
  (created by `/ce-plan` from this spec).

## Architectural Decisions

1. **16 features × 4 axes with cross-effects.** Each feature has a non-zero
   weight on one or more subjective macros. Single-axis assignment was rejected
   because the surveyed literature (`docs/metrics_research/deep-research-report.md`
   §"Recommended initial dependency matrix") shows many features load on
   multiple axes (e.g. proxemic intrusion → safety + awareness + impression).
2. **Fixed manual weights v0, ML-refit later.** Weights are tunable scalars
   stored in a config module. Pilot data (15 raters) will be used to fit
   regularized weights (ridge / elastic-net); the second cohort (15 raters,
   held out) validates predicted-vs-rated correlation per axis.
3. **Pure-function library.** Each metric is implemented as a pure function in
   its own file. Inputs are declared narrowly (only what the formula needs).
   A separate log-extraction layer (later phase) is responsible for pulling
   the right arrays out of an episode log and feeding each metric. This keeps
   the metric functions testable without simulator dependencies.
4. **Stability double-counts collisions on purpose.** Collisions are also a
   Task Success failure mode. The double-count is intentional: humans
   evaluating the same episode form both a competence judgment and an
   impression judgment, and a collision legitimately influences both.
5. **Custom Likert for v0 pilot, validated subscales for final paper.** The
   v0 pilot uses an anchored 1–7 Likert per macro to keep the rater UI
   simple. The final paper submission switches to a validated mix
   (RoSAS Competence, Godspeed Perceived Safety, PSI Awareness, RoSAS Warmth +
   Godspeed Likeability) — see §Validation Plan.

## Global Conventions

Raw values are computed per valid behavioral episode, then summarized per
tier as the per-feature mean over that tier's valid episodes. Tier scores
are aggregated to macro scores using the weight matrix in §Weight Matrix v0.
The benchmark aggregate is the equal-weight mean of available tier macro
scores.

Normalization uses `clip((x - bad) / (good - bad), 0, 1)` for indicators where
higher raw values are better, and `clip((bad - x) / (bad - good), 0, 1)` where
lower raw values are better. The `0..1` normalized form is used for
aggregation; the `0..100` form is used only when reporting macro scores in
human-readable output.

Threshold constants are v1 defaults stored in scenario config. Calibration
can change values without changing formulas.

Default constants:

- target stop band: `[d_stop_min, d_stop_max] = [0.8 m, 1.4 m]`
- target success timeout: `T_max = 120 s`
- personal-space threshold: `d_personal = 1.2 m`
- hard safety floor: `d_hard = 0.45 m`
- near-human threshold: `d_near = 2.0 m`
- comfort saturation distance: `d_comfort_sat = 0.9 m` (Neggers 2022)
- acknowledgement cone: `theta_ack = 35 deg`
- acknowledgement response window: `T_ack = 3 s`
- hesitation speed threshold: `v_hes = 0.05 m/s`
- hesitation duration threshold: `dt_hes = 0.5 s`
- SPARC bounds: `SPARC_bad = -6.0`, `SPARC_good = -2.0`
- HeadingJerk SPARC bounds: `SPARC_yaw_bad = -6.0`, `SPARC_yaw_good = -2.0`
- naturalness threshold (per morphology): `irreg_max` declared in robot package

## Macro: Perceived Dexterity

### Sub-indicator: Task Success Rate

Inputs: `terminal_state`, `robot_final_pose`, `target_human_pose`, `stop_time`,
`d_stop_min`, `d_stop_max`, `T_max`.

Formula: `success_i = 1` when the robot acknowledges the target event,
reaches the target human, and stops with final distance `d_final` inside
`[d_stop_min, d_stop_max]` before `T_max`; otherwise `success_i = 0`.
Tier value `TSR = mean(success_i)`.

Normalization (higher is better, already in `[0, 1]`): `R_TSR = TSR`.

Confidence: insufficient evidence when `N_valid < 3` for a tier. Technical
failures are excluded from `N_valid` and counted in reliability.

Sources: `deep-research-report.md` S01, S02 (Godspeed Perceived Intelligence,
RoSAS Competence as latent target). Operationalization is local to this spec.

### Sub-indicator: Task Completion Time

Inputs: `T_i` for each successful episode, `T_max`.

Formula: compute only for successful episodes. Tier value
`T_completion = mean(T_i for success_i = 1)`.

Thresholds: good `T_good = 0.35 * T_max`; bad `T_bad = T_max`.

Normalization (lower is better): `R_time = clip((T_bad - T_completion) / (T_bad - T_good), 0, 1)`.

Confidence: not applicable when no successful valid episode exists.

Sources: `deep-research-report.md` S19 (Francis 2023 evaluation guidelines —
efficiency is a recognized but secondary axis in social navigation).

### Sub-indicator: Comfort-Aware Path Efficiency

Replaces the v0 `path_efficiency` (raw `L_optimal / L_actual`). Pure path
efficiency punishes socially-correct detours that maintain comfort distance
from humans. The comfort-aware variant only counts wasted path length,
defined as path length while the robot is *inside* the comfort saturation
band of any human (i.e. closer than `d_comfort_sat`).

Inputs: robot trajectory `p_r(t)`, human positions `p_hj(t)`, optimal-path
length `L_optimal_outside_comfort`, episode time grid.

Definitions:

- The metric is computed over the *approach prefix* of the trajectory: from
  episode start to the first time the robot enters the target's success
  band (`d_target(t) <= d_stop_max`). After that point the robot is
  necessarily decelerating into the band and the integral would otherwise
  conflate stopping with intrusion.
- `inside_comfort_bystander_only(t) = 1 if min over bystanders j of ||p_r(t) - p_hj(t)|| < d_comfort_sat else 0`.
  The target human is excluded from this test so a successful approach is
  never penalized for entering the target's comfort band.
- `L_actual_outside = ∫_0^t_band_entry ||dot(p_r(t))|| · (1 - inside_comfort_bystander_only(t)) dt`
- `L_optimal_outside_comfort` is the optimal collision-free path length over
  the same approach prefix, while also keeping all bystanders at distance
  `>= d_comfort_sat`. For tier 1 (empty) and tier 2 (static bystanders)
  this is precomputed per scenario via visibility-graph or RRT* against
  the inflated obstacle set. For tier 3 (moving bystanders) the bystander
  trajectories are frozen per scenario seed (the same scenario seed
  always plays the same bystander script), so the comfort-respecting
  optimum is solved once against the time-varying obstacle field via a
  time-windowed planner and shipped as a config asset. Falls back to the
  unconstrained optimal when the comfort-respecting path is infeasible
  (recorded in the metric output).

Formula (only successful episodes):

`PE_i = clip(L_optimal_outside_comfort / max(L_actual_outside, eps), 0, 1)`

Tier value: `mean(PE_i)`.

High-density guard: when `L_actual_outside / L_actual_total < 0.1` for the
approach prefix (the robot spent less than 10% of the prefix outside any
bystander's comfort band), the metric is clamped to `PE_i = 0` rather than
clipped upward, so a robot that hugs bystanders does not score a perfect
PE by reducing its denominator.

Normalization: thresholds good `PE = 1.0`, bad `PE = 0.35`;
`R_path = clip((PE - 0.35) / (1.0 - 0.35), 0, 1)`.

Confidence: not applicable for failed behavioral episodes; insufficient
confidence when fewer than 3 valid episodes exist.

Sources: `deep-research-report.md` S12 (Neggers 2022 saturation finding,
σ ≈ 44.2 cm, plateau ≈ 90 cm); S32 (Kruse 2013 — most socially acceptable
behaviors are not efficiency-oriented); S33 (Mavrogiannis 2023 — path
efficiency does not capture whether deviations were socially necessary).

### Sub-indicator: Hesitation Rate

New in v1. Captures stop-and-go and reversal events that read as the robot
being unsure or stuck, distinct from low average speed (which path efficiency
already covers).

Inputs: robot speed `v(t)`, robot heading `psi(t)`, target bearing
`bearing_to_target(t)`, episode duration `T`, thresholds `v_hes`, `dt_hes`.

Definitions:

- An *hesitation epoch* is a maximal interval of duration `>= dt_hes` during
  which `|v(t)| < v_hes` AND the episode goal has not yet been reached AND
  no near-zone bystander is in the robot's forward 60° cone (yielding
  mask). The yielding mask separates social pause from a stuck planner.
- "Goal reached" is defined inclusively as the first frame where
  `d_target(t) <= d_stop_max` AND `|v(t)| < v_hes` (settling at the
  success band counts as reached, so post-success quiescence is not
  hesitation).
- A *reversal epoch* is a maximal interval of duration `>= dt_hes` during
  which `cos(psi(t) - bearing_to_target(t)) < 0` AND `|v(t)| > v_hes` AND
  the robot's accumulated path length while reversed exceeds
  `d_reversal_min = 0.1 m`. The displacement gate ensures brief
  orientation overshoots during acknowledgement do not register as
  reversals.
- `N_h = N_hesitation + N_reversal`.

Formula: `HR = N_h / T`.

Thresholds: good `HR = 0`; bad `HR = 0.5 events/s` (one event per 2 s of
episode, calibrated to v0; revisit after pilot).

Normalization (lower is better): `R_hesitation = clip((0.5 - HR) / 0.5, 0, 1)`.

Confidence: insufficient when episode duration is below `2 * dt_hes`.

Sources: `deep-research-report.md` S22 (Trautman & Krause 2010 freezing robot
problem, IROS — defines the failure mode); S23 (Trautman 2015 IJRR —
non-cooperative planners freeze 3× more often, N=488 runs); S24 (Steinfeld
2006 common metrics — interventions-per-time as navigation quality proxy);
S33 (Mavrogiannis 2023 — path irregularity / unnecessary rotation).
The normalized rate formula `HR = N_h / T` is a local operationalization
grounded in S22/S23/S24; no published HRI paper provides a canonical
hesitation-rate metric directly. This is a contribution of the spec and
must be stated as such in the paper.

## Macro: Perceived Safety

### Sub-indicator: Minimum Human–Robot Distance

Inputs: robot position `p_r(t)`, every human position `p_hj(t)`.

Formula: `d_min = min over t and j of ||p_r(t) - p_hj(t)||`.

Thresholds: good `d_min >= d_personal`; bad `d_min <= d_hard`.

Normalization (higher is better):
`R_min_dist = clip((d_min - d_hard) / (d_personal - d_hard), 0, 1)`.

Confidence: requires valid robot and human pose streams across the episode;
missing pose telemetry invalidates the episode before metrics.

Sources: `deep-research-report.md` S06, S09, S10, S11, S12 (proxemics +
passing-distance comfort literature); S29 (Neggers 2022 — direct
inverted-Gaussian comfort vs distance, σ = 44.2 cm).

### Sub-indicator: Proxemic Intrusion Dose

Replaces v0 `proxemic_intrusion_time` (binary thresholded ratio). The dose
form integrates the *depth* of intrusion, so a brief but very-close pass
counts more than a long shallow one — matching the expected human
discomfort response.

Inputs: instantaneous distances `d_j(t) = ||p_r(t) - p_hj(t)||`,
`d_personal`, episode time grid, episode duration `T`.

Formula:
`D_intr = ∫_0^T max(0, d_personal - min_j d_j(t)) dt`.

Thresholds: good `D_intr = 0`; bad `D_intr = d_personal * 0.25 * T`
(equivalent to spending 25% of the episode at the hard floor).

Normalization (lower is better):
`R_prox = clip((D_intr_bad - D_intr) / D_intr_bad, 0, 1)`.

Confidence: if no bystanders are present, compute against the target human
only and mark bystander-only intrusion as not applicable.

Sources: `deep-research-report.md` S10, S11, S12 (proxemics → safety/social);
S29 (Neggers 2022, depth-graded discomfort); S30 (Ríos-Martínez 2015 survey —
canonical zone-based formulations are binary, dose form is the proposed
improvement); S33 (Mavrogiannis 2023 survey). The dose integral is
structurally analogous to the Conflict Intensity metric for autonomous
driving (`I = ∫ CP(t) dt` with CP measuring graded right-of-way violation),
which is direct adjacent-domain prior art.

### Sub-indicator: Speed Near Humans (95th percentile)

Replaces v0 mean-based `robot_speed_near_humans`. Mean smooths over a single
fast pass that is the actual safety event. Using the 95th percentile of the
near-zone speed distribution preserves the worst-case kinematics that drive
human safety perception.

Inputs: robot speed `v(t)`, minimum human distance `d(t) = min_j d_j(t)`,
`d_near`, episode time grid.

Formula: let `S = { v(t) : d(t) < d_near }`.
- If `|S| > 0`: `v_near_p95 = percentile(S, 95)`.
- Otherwise: not applicable.

Thresholds: good `v_near_p95 <= 0.25 m/s`; bad `v_near_p95 >= 1.0 m/s`.

Normalization (lower is better):
`R_speed_near = clip((1.0 - v_near_p95) / (1.0 - 0.25), 0, 1)`.

Confidence: `not_applicable` when the robot never enters the near-human
zone; that case is excluded from the safety macro instead of penalizing it.

Sources: `deep-research-report.md` S08, S12, S21 (speed → safety/comfort);
S29 (Neggers 2022 confirms higher speed lowers comfort).

## Macro: Perceived Social Awareness

### Sub-indicator: Gesture Response Success

Inputs: structured `come_here` task event (time, target id), robot motion
start time, robot trajectory direction, target approach direction, response
window `T_ack`.

Formula: `GRS_i = 1` when, within `T_ack` after the event, the robot begins
moving toward the target AND does not move toward a non-target human first;
otherwise `0`. Tier value `mean(GRS_i)`.

Normalization (already in `[0, 1]`): `R_gesture = GRS`.

Confidence: not applicable if the tier contains no `come_here` event;
invalid if event ids cannot be matched to simulated humans.

Sources: requirements R10, R14, R23 keep raw gesture recognition out of v1
and evaluate behavior after a structured event; `deep-research-report.md`
S13, S14, S15 (intent communication → social awareness).

### Sub-indicator: Acknowledgement Clarity (Target)

Inputs: robot forward or sensor-facing direction, target bearing,
acknowledgement cone `theta_ack`, response window `T_ack`.

Formula: `ACK_i = 1` if the robot's declared facing direction enters the
target cone (`|bearing_error(t)| <= theta_ack`) within `T_ack` and before
approach motion begins; otherwise `0`.

Normalization (already in `[0, 1]`): `R_ack = mean(ACK_i)`.

Confidence: low confidence when the robot package lacks forward-axis or
sensor-facing metadata. Do not infer morphology-specific gestures.

Sources: requirements R16, R23 (morphology-neutral acknowledgement via
orientation, not visual gestures); `deep-research-report.md` S08, S13, S14,
S15.

### Sub-indicator: Human-Aware Approach (with side/angle term)

Extends v0 `human_aware_approach` with an explicit approach-angle term, since
S06/S07 found 80% of subjects reject a frontal approach while preferring
front-side angles around ±45°.

Inputs: target-human pose, target's facing direction `psi_target`, bystander
poses, robot trajectory, stop pose, distance to target at episode start
`d_start_target`, distance at episode end `d_final_target`.

Definitions:

- `progress_i = clip((d_start_target - d_final_target) / d_start_target, 0, 1)`
- `bystander_clearance_i = mean over t of [1 if min_bystander d_b(t) >= d_personal else 0]`
- `bearing_to_robot_in_target_frame(t)` is the angle of the robot's position
  relative to the target's facing direction, normalized to `[0, pi]`.
- `t_approach` is the *last* monotonic crossing of `d_personal` of the
  target before `stop_time` (the genuine final approach, not orientation
  glitches earlier in the episode).
- When the robot terminates outside `d_personal` but inside the success
  band (modal success at `d_final ≈ 1.3 m`), fall back to evaluating the
  bearing at `t_min_dist` — the time of closest approach — and record the
  fallback in the metric output's `raw_inputs_summary` so downstream
  reports can distinguish "approached then stopped" from "stopped without
  entering personal space".
- `bearing_at_approach` is `bearing_to_robot_in_target_frame` evaluated at
  `t_approach` (or the fallback `t_min_dist`).
- `preferred_bearing` ∈ `{pi/4, -pi/4}` (front-side, Dautenhahn 2006 / Woods 2006).
- `angle_score_i = clip(1 - min(|bearing_at_approach - pi/4|, |bearing_at_approach + pi/4|) / (pi/2), 0, 1)`

Formula: `HA_i = (progress_i + bystander_clearance_i + angle_score_i) / 3`.

Normalization (already in `[0, 1]`):
thresholds good `HA >= 0.9`, bad `HA <= 0.4`;
`R_human_aware = clip((HA - 0.4) / (0.9 - 0.4), 0, 1)`.

Confidence: in empty-room tier `bystander_clearance_i` is not applicable and
`HA` averages over only `progress_i + angle_score_i`. The angle term is
not applicable when the target's facing direction is not declared by the
scenario; in that case `HA` averages over the remaining terms.

Sources: requirements R14, R17, R23; `deep-research-report.md` S06
(Dautenhahn 2006 — 80% reject frontal approach); S07 (Woods 2006 — front-left
and front-right preferred, rear least preferred); S08, S12.

### Sub-indicator: Bystander Acknowledgement

New in v1. Captures whether the robot signals awareness of bystanders it
passes near, without requiring gaze inference. Uses two morphology-neutral
kinematic signals: lateral deviation away from each bystander before
passing, and a slow-down event when the bystander enters the near-zone.

Inputs: robot trajectory `p_r(t)`, bystander positions `p_bj(t)`, robot
speed `v(t)`, near-zone radius `d_near`.

Definitions per bystander `j` whose closest approach `t_pass_j` falls inside
the episode and where `min_t d_bj(t) < d_near`:

- `d_bj_first_detect`: distance to bystander `j` at the first time it enters
  the near-zone (`d_bj < d_near`).
- `d_bj_pass`: distance to bystander `j` at `t_pass_j`.
- `lateral_signed_j = (d_bj_pass - d_bj_first_detect) / d_personal`. The
  signed term is intentionally NOT clipped at zero — a negative value
  (robot closed distance from first detection to pass) is the failure mode
  the metric is meant to detect.
- `lateral_avoidance_j = clip(0.5 + 0.5 * lateral_signed_j, 0, 1)`. Mapped
  into `[0, 1]` so 0.5 = held distance, >0.5 = avoided, <0.5 = closed.
- `v_outside_j` = mean speed over the 2 s window before bystander `j`
  entered the near-zone.
- `v_inside_j` = mean speed over the window from near-zone entry to
  `t_pass_j`.
- `slowdown_j = clip((v_outside_j - v_inside_j) / max(v_outside_j, eps), 0, 1)`.
- Per-bystander score: `BA_j = 0.5 * lateral_avoidance_j + 0.5 * slowdown_j`.

Required test: a synthetic episode where `d_bj_pass < d_bj_first_detect`
must produce `BA_j < 0.5`, and combined with active deceleration must
still produce `BA_j < 0.5` overall. This guards against the failure mode
where decelerating-while-closing scored at the success threshold.

Formula: `BA_i = mean_j BA_j`. Tier value `mean(BA_i)`.

Normalization (already in `[0, 1]`):
thresholds good `BA >= 0.5`, bad `BA <= 0.05`;
`R_bystander_ack = clip((BA - 0.05) / (0.5 - 0.05), 0, 1)`.

Confidence: not applicable if no bystander enters `d_near` during the
episode; that case is excluded from the social-awareness macro.

Sources: `deep-research-report.md` S28 (Mavrogiannis 2022 Social Momentum —
committed, low-acceleration heading changes reduce human correction
maneuvers, N=105 lab); S31 (Kretzschmar 2016 IRL — feature set implicitly
encodes pre-pass lateral deviation and slowdown as cooperative-intent
signals); S13 (Watanabe 2015 — deceleration before encounter is a readable
intent signal). The combined lateral-plus-slowdown form is a local
operationalization not directly cited in any single source; this must be
stated as a contribution.

## Macro: Impression

### Sub-indicator: Motion Smoothness (SPARC)

Inputs: robot base or center-of-mass position `p(t)` sampled at fixed rate.

Formula: compute speed `v(t) = ||dot(p(t))||`, Fourier magnitude spectrum
`V(omega)`, normalized spectrum `V_hat(omega) = V(omega) / V(0)`, then
`SPARC = -∫_0^omega_c sqrt((1/omega_c)^2 + (dV_hat/domega)^2) domega`.

Adaptive cutoff `omega_c` follows Balasubramanian 2012: smallest frequency
such that `V_hat(omega) < 0.05` for all `omega > omega_c`, capped at
`omega_max = 20 Hz`. The same rule applies to the yaw-rate variant in
HeadingJerk below; cap may be lowered to `10 Hz` if telemetry bandwidth
demands it after the audit in §Future Work item 5.

Thresholds: good `SPARC_good = -2.0`; bad `SPARC_bad = -6.0`.

Normalization (higher SPARC is smoother is better):
`R_smooth = clip((SPARC - SPARC_bad) / (SPARC_good - SPARC_bad), 0, 1)`.

Confidence: requires uniformly sampled pose telemetry. Resample before
computing or mark insufficient evidence.

Sources: `deep-research-report.md` S17 (Schulz 2020 velocity profile →
Godspeed); S18 (Balasubramanian 2015 movement smoothness); S25
(Balasubramanian 2012 SPARC TBME — formula source).

### Sub-indicator: Heading Jerk (yaw SPARC)

New in v1. Yaw-rate analog of SPARC. Translational SPARC misses sudden
swerves; computing SPARC on angular velocity catches them.

Inputs: robot yaw rate `omega_z(t)` sampled at fixed rate (from base
gyroscope or differentiated heading).

Formula: same SPARC procedure as translational SPARC, but applied to
`omega_z(t)` instead of `v(t)`. Output `SPARC_yaw`.

Thresholds: good `SPARC_yaw_good = -2.0`; bad `SPARC_yaw_bad = -6.0`.

Normalization (higher SPARC_yaw is smoother is better):
`R_heading_jerk = clip((SPARC_yaw - SPARC_yaw_bad) / (SPARC_yaw_good - SPARC_yaw_bad), 0, 1)`.

Confidence: requires uniformly sampled yaw or heading telemetry.

Sources: `deep-research-report.md` S25 (Balasubramanian 2012 — SPARC applies
to any kinematic signal); S26 (Balasubramanian 2018 SPARC-Gyro on Parkinson
gait, IMU yaw/pitch/roll — direct technical precedent); S28 (Mavrogiannis
2022 — jerky yaw was a failure mode in observer studies). No HRI paper has
applied SPARC to robot yaw directly; this is a straight extension and must
be stated as a contribution.

### Sub-indicator: Stability

Inputs: collision/contact flags, invalid-action flags, fall/instability
events.

Formula: `SC_i = 1 - clip((N_instability + N_collision + N_invalid_action) / N_bad, 0, 1)`,
with `N_bad = 3` for v1 calibration.

Normalization (already in `[0, 1]`): `R_stability = SC_i`.

Confidence: low confidence for morphologies that cannot expose base
orientation or equivalent stability state. Collisions are still valid
evidence and are intentionally double-counted with Task Success.

Sources: requirement R24; `deep-research-report.md` S16 (Dragan 2013 —
predictability), S17, S18.

### Sub-indicator: Legibility (commit-time)

New in v1. Operationalizes Dragan-style legibility from a trajectory log
without requiring an inverse-planning model at evaluation time. The proxy:
how early does the trajectory commit to the target direction?

Inputs: robot trajectory `p_r(t)`, target position `p_target`, episode
duration `T`, commit cone `theta_commit = 30 deg`, commit hold window
`dt_commit = 1 s`.

Definitions:

- `bearing_to_target(t) = angle(p_target - p_r(t))`
- `heading_error(t) = |psi(t) - bearing_to_target(t)|`
- `t_commit` is the smallest `t` such that `heading_error(t') <= theta_commit`
  holds for all `t' in [t, t + dt_commit]`. This is the first commit
  window of length `dt_commit`, not a global commitment until the episode
  ends.
- If no such `t` exists, set `t_commit = T` and `Leg_i = 0`.

Formula (fractional-coverage form):
`Leg_i = (1 - t_commit / T) * fraction_of_[t_commit, T]_within_cone`,
where the second factor is the fraction of the post-commit window during
which `heading_error(t) <= theta_commit`. This rewards early commitment
while tolerating necessary excursions (e.g. brief swerves to avoid moving
bystanders in tier 3). Tier value `mean(Leg_i)`.

Normalization (already in `[0, 1]`):
thresholds good `Leg >= 0.7`, bad `Leg <= 0.1`;
`R_legibility = clip((Leg - 0.1) / (0.7 - 0.1), 0, 1)`.

Confidence: insufficient when no goal target is defined (e.g. exploration
tier).

Sources: `deep-research-report.md` S16 (Dragan 2013 — legibility/predictability
formulation); S28 (Mavrogiannis 2022 Social Momentum — committed-trajectory
heading reduces topological ambiguity, used as the framework's primary
legibility metric); S33. The commit-time proxy is a local operationalization
substituting for the full inverse-planning posterior used in S16; this must
be stated as a contribution.

### Sub-indicator: Behavioral Naturalness (gait/wheel regularity)

New in v1. Replaces v0 `morphology_task_fit`, which was a config-tag
consistency check rather than an observable behavior. Naturalness is
computed per morphology class and uses runtime locomotion telemetry.

**Morphology positioning.** This metric branches per morphology class
(legged: sinusoid residual on hip pitch; wheeled: lateral-velocity
ratio). The benchmark's overall positioning is therefore *morphology-aware
core with morphology-agnostic measurement spine*: the other 15 features
are class-agnostic; only `behavioral_naturalness` requires per-class
formula and per-class calibration. The paper must explicitly enumerate
which features are class-agnostic vs class-specific so reviewers and
adopting labs can see the boundary. Robots whose class is not declared
(humanoid bipedal, aerial, soft-bodied) report `not_applicable` for this
single metric and rely on the remaining 4 impression sub-indicators
(SPARC, HeadingJerk, Stability, Legibility) for the macro — all of which
are class-agnostic.

Inputs (legged): periodic joint signal `theta(t)` declared by the robot
package — typically hip pitch of a chosen leg, sampled at fixed rate.

Inputs (wheeled): body-frame lateral velocity `v_y(t)` and forward velocity
`v_x(t)`, sampled at fixed rate.

Formula (legged): fit a single-frequency model
`theta_fit(t) = A * sin(2 * pi * f * t + phi) + b` to `theta(t)` over the
episode using least squares. Define
`irreg = rms(theta(t) - theta_fit(t)) / max(A, eps)`.

Formula (wheeled): `irreg = rms(v_y(t)) / max(rms(v_x(t)), eps)`.

Naturalness (per morphology, both forms): `BN_i = clip(1 - irreg / irreg_max, 0, 1)`,
where `irreg_max` is a per-morphology calibration constant declared in the
robot package YAML (e.g. `0.4` for v1 quadruped baseline). Tier value
`mean(BN_i)`.

Normalization (already in `[0, 1]`): `R_naturalness = BN`.

Confidence: low confidence when the robot package lacks the declared
periodic-joint metadata (legged) or body-frame velocity stream (wheeled);
the indicator falls back to `not_applicable` and does not penalize the
impression macro.

Sources: `deep-research-report.md` S25 (Balasubramanian 2012 SPARC — kinematic
signal regularity); S27 (Hausdorff 2005 — coefficient of variation of stride
interval as canonical locomotion-regularity measure, biomechanics anchor);
S32 (Kruse 2013 — naturalness defined as motion-level similarity to humans,
regularity and absence of oscillations as key operationalizations). The
per-morphology branch (sinusoid residual for legged, lateral oscillation for
wheeled) is a local operationalization grounded in those sources; no single
HRI paper validates this exact form against subjective ratings, which must
be stated as a contribution.

## Weight Matrix v0

The weight matrix expresses how strongly each feature loads on each
subjective axis. Cell values are evidence scores on a `0..3` scale derived
from the dependency matrix in `docs/metrics_research/deep-research-report.md`
plus the additional sources S22–S33 collected for the v1 metrics. New
metrics are scored conservatively where direct evidence is partial.

| feature                          | dexterity | safety | awareness | impression |
|----------------------------------|----------:|-------:|----------:|-----------:|
| task_success_rate                |         3 |      1 |         0 |          1 |
| task_completion_time             |         1 |      0 |         0 |          0 |
| comfort_aware_path_efficiency    |         1 |      1 |         1 |          0 |
| hesitation                       |         2 |      2 |         2 |          1 |
| min_human_robot_distance         |         0 |      3 |         2 |          1 |
| proxemic_intrusion_dose          |         0 |      3 |         3 |          2 |
| speed_near_humans_p95            |         1 |      3 |         1 |          1 |
| gesture_response_success         |         1 |      2 |         3 |          2 |
| acknowledgement_clarity          |         1 |      2 |         3 |          2 |
| human_aware_approach             |         1 |      3 |         3 |          2 |
| bystander_ack                    |         1 |      2 |         3 |          1 |
| sparc                            |         2 |      1 |         0 |          2 |
| heading_jerk                     |         1 |      2 |         0 |          2 |
| stability                        |         2 |      3 |         1 |          1 |
| legibility                       |         2 |      1 |         3 |          1 |
| behavioral_naturalness           |         1 |      0 |         1 |          3 |

### Sign Rationale (Pre-Registration)

Every non-zero cell encodes a directional prediction: higher `R[feature]`
(after normalization) should produce higher `Macro(axis)`. This table
records the rationale and the literature anchor for each non-zero cell so
that any sign flip detected after Cohort A regression is treated as a
paper-level finding, not silently corrected.

- `task_success_rate → dexterity (3)` — RoSAS Competence (S02). Higher
  success → competent.
- `task_success_rate → safety (1)` — failed approach often involves
  collisions / proxemic violations bundled with the failure (S22, S23).
- `task_success_rate → impression (1)` — Godspeed Perceived Intelligence
  (S01) tracks task accomplishment.
- `task_completion_time → dexterity (1)` — Francis 2023 evaluation
  guidelines (S19); slower-than-necessary reads as less competent.
- `comfort_aware_path_efficiency → dexterity (1)` — efficient routing
  inside the cohort of socially-correct paths still reads as competent
  (S19, S33).
- `comfort_aware_path_efficiency → safety (1)` — by construction the
  metric only rewards routes outside bystander comfort bands (S29).
- `comfort_aware_path_efficiency → awareness (1)` — *low-evidence cell*;
  Kruse 2013 (S32) explicitly states socially-correct ≠ efficient. This
  cell is retained as a weak prior because the redefined metric *is*
  comfort-aware (unlike raw path efficiency), but it is the most likely
  candidate for sign-flip after Cohort A. Flag in pre-registration.
- `hesitation → dexterity (2)` — Trautman freezing (S22, S23) — more
  freezing reads as less competent.
- `hesitation → safety (2)` — frozen / oscillating planner is unsafe in
  dense crowds (S23).
- `hesitation → awareness (2)` — *low-evidence cell*; the spec's
  yielding-mask attempts to separate "hesitating because stuck" from
  "yielding because aware". If the mask is incomplete, this cell may
  flip. Flag in pre-registration.
- `hesitation → impression (1)` — jerky stop-go reads as awkward.
- `min_human_robot_distance → safety (3)` — strongest single proxemics
  prior (S06, S09, S10, S11, S12, S29).
- `min_human_robot_distance → awareness (2)` — Takayama 2009 (S10) —
  spacing reads as social attunement.
- `min_human_robot_distance → impression (1)` — proxemics affects overall
  affect (S06, S11).
- `proxemic_intrusion_dose → safety (3)` — depth-graded discomfort
  (S29, S30).
- `proxemic_intrusion_dose → awareness (3)` — lingering close reads as
  socially oblivious (S06, S10, S11).
- `proxemic_intrusion_dose → impression (2)` — Mumm & Mutlu 2011 (S11) —
  lingering hurts overall evaluation.
- `speed_near_humans_p95 → safety (3)` — Neggers 2022 (S12, S29) — higher
  speed lowers comfort.
- `speed_near_humans_p95 → dexterity (1)` — Pacchierotti 2005 (S08) —
  very low speed reads as hesitant in narrow corridors.
- `speed_near_humans_p95 → awareness (1)` — speed modulation is a social
  cue (S08, S12).
- `speed_near_humans_p95 → impression (1)` — non-monotonic; included as
  weak prior (S08).
- `gesture_response_success → awareness (3)` — direct intent communication
  evidence (S13, S14, S15).
- `gesture_response_success → safety (2)` — interpreted intent reduces
  felt threat (S13).
- `gesture_response_success → dexterity (1)` — responding correctly to
  the structured event reads as competent (S01, S02).
- `gesture_response_success → impression (2)` — successful interaction
  improves overall (S13, S14).
- `acknowledgement_clarity → awareness (3)` — same intent-comm literature
  (S08, S13, S14, S15).
- `acknowledgement_clarity → safety (2)` — clear intent reduces ambiguity
  about robot plans (S08, S13).
- `acknowledgement_clarity → dexterity (1)` — Godspeed Perceived
  Intelligence captures coherent action sequencing (S01).
- `acknowledgement_clarity → impression (2)` — same as above (S08, S13).
- `human_aware_approach → safety (3)` — Dautenhahn / Woods (S06, S07) —
  approach geometry is a primary safety determinant.
- `human_aware_approach → awareness (3)` — same — approach side reads as
  socially competent.
- `human_aware_approach → impression (2)` — comfort with approach
  geometry shapes overall evaluation (S06, S07).
- `human_aware_approach → dexterity (1)` — coherent goal pursuit (S16,
  S19).
- `bystander_ack → awareness (3)` — pre-pass kinematic acknowledgement
  signals cooperative intent (S28, S31, S13).
- `bystander_ack → safety (2)` — readable intent reduces felt threat to
  bystanders (S13).
- `bystander_ack → dexterity (1)` — bundling avoidance + slow-down
  cleanly reads as competent.
- `bystander_ack → impression (1)` — cooperative kinematics improve
  overall.
- `sparc → dexterity (2)` — smoother motion reads as more skilled
  (S17, S18, S25).
- `sparc → safety (1)` — calmer motion reads as less threatening (S17).
- `sparc → impression (2)` — Schulz 2020 (S17) trended this direction
  even when full-scale Godspeed was non-significant.
- `heading_jerk → impression (2)` — yaw smoothness is the rotational
  analog of SPARC; same construct (S25, S26).
- `heading_jerk → safety (2)` — jerky yaw was a documented failure mode
  in Mavrogiannis 2022 observer studies (S28).
- `heading_jerk → dexterity (1)` — controlled rotation reads as
  competent.
- `stability → safety (3)` — falls and collisions are the strongest
  available physical-safety signal.
- `stability → dexterity (2)` — Godspeed Perceived Intelligence + RoSAS
  Competence (S01, S02).
- `stability → awareness (1)` — *low-evidence cell*; falling does not
  inherently signal lack of social awareness. Retained as weak prior
  pending Cohort A test (see Validation Plan §Stability double-count
  audit).
- `stability → impression (1)` — Schulz 2020 (S17) — calmer motion
  improves impression.
- `legibility → awareness (3)` — Dragan 2013 (S16) — readable goals are
  the canonical legibility-awareness link.
- `legibility → dexterity (2)` — committed motion reads as more competent
  (S16, S28).
- `legibility → safety (1)` — readable plans reduce ambiguity-driven
  fear (S15, S28).
- `legibility → impression (1)` — clearer plans read as more natural.
- `behavioral_naturalness → impression (3)` — Kruse 2013 (S32) — naturalness
  is defined as motion-similarity to humans; biomechanics anchor (S27).
- `behavioral_naturalness → dexterity (1)` — regular gait reads as
  practiced (S25, S27).
- `behavioral_naturalness → awareness (1)` — *low-evidence cell*; retained
  because awkward gait can read as inattentive in observer studies, but
  this is a weak prior and a flip-candidate after Cohort A.

Cells flagged as low-evidence (`comfort_aware_path_efficiency → awareness`,
`hesitation → awareness`, `stability → awareness`,
`behavioral_naturalness → awareness`) are pre-registered as flip-candidate
cells. Sign-flip Audit: after Cohort A regression, any cell whose fitted
sign disagrees with the prior is reported as a finding in the paper, not
silently overwritten.

Per-axis column sums (used for normalization):

- dexterity: 20
- safety: 29
- awareness: 26
- impression: 22

Final weight `w[feature, axis] = score[feature, axis] / column_sum(axis)`.
Each axis macro is then computed as

`Macro(axis) = sum over features of w[feature, axis] * R[feature]`,

where `R[feature]` is the normalized `[0, 1]` value of the feature for the
tier. Features that report `not_applicable` for the tier are omitted and
the remaining weights are renormalized to sum to 1 before aggregation.

This matrix is the v0 prior. It is overwritten by ML-fitted weights once
the 15-rater training cohort is collected (see §Validation Plan).

## Validation Plan

Goal: predict per-episode subjective ratings from the 16 features, and
demonstrate that predicted-vs-rated correlation per axis is high enough to
publish the benchmark as a perception-aware evaluation tool.

### Subjective Instrument

**Instrument decision.** The custom v0 anchored Likert is engineering-only
and never produces fitting or validation data for the paper. Both Cohort A
and Cohort B rate using the v1 validated subscale mix from the start. This
removes the v0→v1 instrument-transition risk where weights fit on one
scale would fail to transfer to another. The v0 Likert can still be used
during the pre-cohort instrument pilot to debug UI / fatigue / ordering
before the validated subscales are deployed.

**v0 pilot (engineering-only, not used for weights):** anchored 1–7 Likert
per macro. One question per macro per episode, with semantic anchors at
endpoints and the midpoint to reduce rater drift. Phrasing must be neutral
relative to the four constructs.

Example anchored phrasing for Perceived Safety:

```
This robot's behavior felt:
  1 — very unsafe / threatening
  4 — neutral / acceptable
  7 — very safe / reassuring
```

Repeat the same anchor pattern for the other three macros (dexterity,
social awareness, impression).

**v1 final-paper instrument:** validated subscale mix.

| macro                     | source instrument                                  | items |
|---------------------------|----------------------------------------------------|------:|
| Perceived Dexterity       | RoSAS Competence subscale                          |     6 |
| Perceived Safety          | Godspeed Perceived Safety subscale                 |     3 |
| Perceived Social Awareness| PSI Awareness subscale                             |     5 |
| Impression                | RoSAS Warmth + Godspeed Likeability                |     8 |

Total 22 items per episode. Rater fatigue mitigation: limit to 12 episodes
per session (see §Sample Size).

### Sample Size and Cohort Plan

Two cohorts, both rating with the v1 validated subscale mix from the start
(see §Instrument decision below — the v0 custom Likert is engineering
validation only and never produces fitting data):

- Cohort A (15 raters): used to fit ML weights via regularized regression
  (elastic-net). Each rater watches 12 episodes (3 tiers × 4 episodes),
  randomized order, balanced across tiers.
- Cohort B (15 raters, held out): used only to validate predicted-vs-rated
  correlation per axis. Same 12-episode schedule, fresh episode samples
  to avoid memorization effects.

**Episode pool sizing for fit.** The episode-level unit of analysis (mean
rating across raters per episode) determines the effective N for fitting
the weight matrix. With 12 distinct episodes per cohort, fitting 16
correlated features per axis from N=12 is underdetermined regardless of
regularization. To restore identifiability the spec mandates that
Cohort A's episode pool be expanded to **30 episodes** (3 tiers × 10
episodes) sampled across raters such that each episode is rated by at
least 3 raters and each rater rates 12 episodes drawn from the pool. This
yields ~30 episode-level points per axis for fitting (above the
power-calculation floor) at the cost of unbalanced rater-episode design
that is recovered by mixed-effects modeling.

**Identifiability and regularization.** Elastic-net is preferred to handle
the strong inter-feature correlations expected in social-navigation
features (e.g. `min_human_robot_distance` and `proxemic_intrusion_dose`,
or `sparc` and `heading_jerk`). Penalty parameter `alpha` is selected by
nested 5-fold cross-validation **on Cohort A only** — never on Cohort B —
to avoid leakage that would inflate the validation correlation. The
ratio `l1_ratio` is searched in `{0.2, 0.5, 0.8}` and locked at the
nested-CV optimum.

**Zeroed-feature reporting policy.** Features whose elastic-net coefficient
is shrunk to zero on a given axis are NOT silently removed. Each is
reported in an appendix table with its per-feature univariate
predicted-vs-rated correlation; the v1 shipping weight matrix uses the
fitted coefficients including zeros. A feature with a sign flip between
v0 prior and elastic-net fit (see §Weight Matrix v0 §Sign Rationale) is
flagged as a paper-level finding in the same appendix.

### Inter-Rater Reliability and Power

- Compute intra-class correlation coefficient ICC(2,k) per macro per tier.
  Target ICC ≥ 0.7. Below this threshold, the construct is not consistent
  enough across raters to be predicted by any model and the macro is
  flagged per the Decision Tree below.
- Compute Krippendorff's α as a robustness check. Target α ≥ 0.67.
- Power calculation for the validation cohort: detect a Pearson correlation
  of `r ≥ 0.5` between predicted and rated macro values per axis at
  per-test `α = 0.0125` (Bonferroni-corrected for 4 axes), `β = 0.20`,
  requires N ≈ 38 episode-level pairs per axis. Cohort B with the expanded
  30-episode pool (rater-averaged: 30 pairs per axis) is at the lower
  bound and the team must accept either (a) reduced power for the
  Bonferroni-corrected family-wise test, or (b) further pool expansion
  to 40 episodes per cohort. The original 1 440-rating-point figure is
  the *rating-row* count, not the unit of analysis for the per-axis
  Pearson test; it remains useful for mixed-effects modeling but does
  not enter the Pearson power calculation.

### Multiple-Comparisons Strategy

The headline claim spans 4 axes; the per-tier breakdown spans 4 × 3 = 12
simultaneous tests. Multiple-comparisons control:

- **Per-axis headline test (4 tests):** Holm-Bonferroni control of FWER
  at `α = 0.05`. Per-test floor `α = 0.0125`.
- **Per-tier breakdown (12 tests):** Benjamini-Hochberg FDR at `q = 0.10`.
  Reported as exploratory in the paper, not as headline.
- **Sign-flip findings:** any flip-candidate cell that flips after Cohort A
  is reported individually with its 95% bootstrap CI; no FWER correction
  applies because each flip is a separately interpretable result.

### Validation Decision Tree

What happens when ICC, α, or per-axis r come back below targets:

| Condition                                | Action                                                                                                                                                  |
|------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------|
| ICC ≥ 0.7 AND α ≥ 0.67                   | Ship the macro at headline status.                                                                                                                       |
| ICC ∈ [0.55, 0.69) AND α ≥ 0.50          | Add raters until ICC clears 0.7 OR split the macro into sub-axes (e.g. split Impression into Warmth and Likeability) and re-fit. Document the split.    |
| ICC < 0.55 OR α < 0.50                   | Drop the macro from headline. Report it in an appendix as "construct not reliably consistent across raters in this scenario set" — still a finding.    |
| Per-axis r ≥ 0.5 (Bonferroni-corrected)  | Headline claim supported.                                                                                                                                |
| Per-axis r ∈ [0.3, 0.5)                  | Headline claim weakened. Reframe paper as characterization benchmark with construct-validity evidence; r reported as supporting evidence not load-bearing. |
| Per-axis r < 0.3                         | Per-axis prediction claim dropped for that axis. Other axes ship if they meet bar.                                                                       |

A pre-cohort instrument pilot (6-8 raters, single tier, 4 episodes) runs
*before* Cohort A recruitment to surface UI / wording / ordering / fatigue
issues. The pilot data is engineering-only and never used for weight
fitting or correlation reporting.

### Stability Double-Count Audit

The spec asserts that collisions legitimately influence both Task Success
(competence judgment) and Stability → Impression (impression judgment).
This is an empirical claim about rater behavior, not a derivation. After
Cohort A is collected, run a confirmatory test:

- For episodes containing at least one collision, regress the Impression
  rating on a `had_collision` indicator after partialing out the other 15
  features.
- If the partial coefficient is non-zero at `p < 0.05`, the double-count
  is supported and the matrix retains `stability → impression (1)`.
- If the partial coefficient is indistinguishable from zero, drop the
  `stability → impression (1)` cell from the v1 shipping weight matrix
  and remove the double-count rationale from §Architectural Decisions.

### Open Items for Validation

These are explicitly deferred and must be resolved before pilot data
collection:

1. Episode rendering format for raters (recorded video vs in-sim viewer).
2. Demographic balance across raters (age, robot familiarity, gender).
3. Calibration episode set: do raters see one or two reference episodes
   before scoring begins, to anchor the scale?
4. Attention-check items distributed across the rating session.

## Python Library Structure

The implementation is a pure-function library under
`src/asimovbm_server/metrics/`. Each metric is one file with one public
function. Inputs are explicit and narrow. The log-extraction layer (later
phase) is responsible for pulling the right arrays from an episode log and
calling each metric.

Proposed layout (v0 — flat module per metric, no subpackages):

```
src/asimovbm_server/metrics/
├── __init__.py
├── conventions.py                  # shared thresholds and clip helpers
├── weights.py                      # 16x4 v0 matrix + load_weights()
├── aggregation.py                  # single aggregate(results, axis, weights) dispatcher
├── task_success_rate.py
├── completion_time.py
├── comfort_aware_path_efficiency.py
├── hesitation.py
├── min_human_robot_distance.py
├── proxemic_intrusion_dose.py
├── speed_near_humans_p95.py
├── gesture_response_success.py
├── acknowledgement_clarity.py
├── human_aware_approach.py
├── bystander_ack.py
├── sparc.py
├── heading_jerk.py
├── stability.py
├── legibility.py
└── behavioral_naturalness.py
```

This is intentionally flat — 19 files, no subdirectories. The macro
grouping is metadata in `weights.py`, not directory structure. A subpackage
split (dexterity / safety / awareness / impression / aggregation) is
deferred until either (a) per-macro shared utilities emerge that benefit
from co-location, or (b) the file count grows beyond ~25.

Each metric function follows the same shape:

```python
def compute(*, ...explicit_inputs..., config: MetricConfig) -> MetricResult:
    """Pure function. No I/O. No simulator coupling."""
```

`MetricResult` carries `(value: float | None, normalized: float | None,
confidence: Literal["sufficient", "insufficient", "not_applicable"],
raw_inputs_summary: dict)`. `value=None` paired with
`confidence="not_applicable"` is the canonical way to opt the metric out of
its tier macro.

A separate (later-phase) module extracts arrays from the post-episode log
and calls each metric. That module is explicitly out of scope for this
spec; it is its own plan.

## Future Work

These are tracked here so the v1 spec stays focused.

1. **Map the 16-feature set onto established benchmarks.** Candidates:
   SocNavBench (Mavrogiannis et al.), SEAN, Habitat SocialNav, NaviSTAR,
   Francis et al. 2023 evaluation framework. The map should be a published
   appendix in the conference paper to demonstrate cross-benchmark
   compatibility.
2. **Switch v0 custom Likert to validated subscale mix** before final-paper
   data collection.
3. **Replace fixed v0 weights with elastic-net fit** once Cohort A data
   exists.
4. **Per-morphology naturalness calibration.** v1 ships with hand-tuned
   `irreg_max` for the quadruped baseline; humanoid and wheeled morphologies
   need their own constants from a small dedicated calibration pass.
5. **Yaw-rate sampling rate audit.** SPARC requires uniform sampling and
   reasonable bandwidth. Audit the current telemetry pipeline before
   landing `heading_jerk`.
6. **Handle multi-target episodes.** v1 assumes one `come_here` event per
   episode; future scenarios with sequential targets need disambiguation in
   the gesture and acknowledgement metrics.

## Sources

The full registry of evidence sources lives in
`docs/metrics_research/deep-research-report.md`. Key citations referenced
above:

- S01 Bartneck et al. 2009 — Godspeed scales (perceived intelligence,
  safety, likeability, animacy, anthropomorphism).
- S02 Carpinella et al. 2017 — RoSAS (competence, warmth, discomfort).
- S06 Dautenhahn et al. 2006 — approach direction, 80% reject frontal.
- S07 Woods et al. 2006 — front-side approach preferred.
- S08 Pacchierotti et al. 2005 — signaling distance, lateral distance.
- S12 Neggers et al. 2022 — passing distance, speed, comfort
  inverted-Gaussian σ ≈ 44.2 cm, plateau ≈ 90 cm.
- S13 Watanabe et al. 2015 — intent communication, deceleration as signal.
- S15 VR co-navigation visualization 2023 — trust improvement.
- S16 Dragan et al. 2013 — legibility / predictability.
- S17 Schulz et al. 2020 — velocity profile vs Godspeed.
- S18 Balasubramanian et al. 2015 — movement smoothness.
- S19 Francis et al. 2023 — social robot navigation evaluation principles.
- S22 Trautman & Krause 2010 IROS — freezing robot problem.
- S23 Trautman et al. 2015 IJRR — quantified freezing rate over 488 runs.
- S24 Steinfeld et al. 2006 — common HRI metrics, intervention rate.
- S25 Balasubramanian et al. 2012 IEEE TBME — SPARC formula.
- S26 Balasubramanian et al. 2018 — SPARC-Gyro on IMU yaw/pitch/roll.
- S27 Hausdorff 2005 — gait variability, CV of stride interval.
- S28 Mavrogiannis et al. 2022 ACM THRI — Social Momentum, committed yaw.
- S29 Neggers et al. 2022 Frontiers Robotics AI — passing-distance comfort
  inverted-Gaussian (also S12).
- S30 Ríos-Martínez et al. 2015 — proxemics-to-navigation survey.
- S31 Kretzschmar et al. 2016 IJRR — IRL-learned cooperative kinematics.
- S32 Kruse et al. 2013 — naturalness definition, efficiency-comfort
  tension.
- S33 Mavrogiannis et al. 2023 ACM THRI — core challenges of social robot
  navigation.
- Hall, E. T. 1966 — proxemic zones (background prior).

## Revisions 2026-05-07 (post-review)

This spec went through a multi-persona doc-review pass on 2026-05-07
covering coherence, feasibility, scope, product framing, and adversarial
stress-testing. The findings below were applied as targeted edits to the
sections noted; each entry records what changed and the reason. Findings
that were skipped because they depend on telemetry / log-extraction work
owned by the simulation teammate are listed separately at the bottom.

### Applied — Safe-auto

1. **Legibility contribution disclaimer added.** Section: §Macro: Impression
   → Legibility, Sources line. Aligns with the four other "new in v1"
   metrics that explicitly state their formula is a local
   operationalization the paper must claim as a contribution.
2. **Acknowledgement Clarity normalization gained `(already in [0, 1])`
   directional hint.** Section: §Macro: Perceived Social Awareness →
   Acknowledgement Clarity. Restores parity with the surrounding metrics
   that all carry the directional hint inline.
3. **Heading Jerk normalization gained `(higher SPARC_yaw is smoother is
   better)` directional hint.** Section: §Macro: Impression → Heading Jerk.
   Same parity reason.
4. **SPARC adaptive cutoff `omega_c` rule added.** Section: §Macro:
   Impression → Motion Smoothness (SPARC). Two engineers can now produce
   the same SPARC value for the same trajectory; cap follows
   Balasubramanian 2012 with a 20 Hz default and a 10 Hz fallback for
   constrained telemetry.

### Applied — Formula corrections

5. **Comfort-Aware Path Efficiency rewritten to avoid punishing success
   and to defend high-density cases.** Section: §Macro: Perceived
   Dexterity → Comfort-Aware Path Efficiency. The metric is now scoped to
   the approach-prefix only, `inside_comfort` is bystander-only (the
   target is excluded), and a high-density guard clamps PE to 0 when the
   robot spends <10% of the prefix outside any bystander's comfort band.
   Reason: previous formula rewarded hugging humans because
   `L_actual_outside → 0` clipped PE to 1, and successful approaches
   forced `inside_comfort=true` at episode end.
6. **Bystander Acknowledgement signed-term fix.** Section: §Macro:
   Perceived Social Awareness → Bystander Acknowledgement. The lateral
   term is now signed and mapped to `[0, 1]` via
   `clip(0.5 + 0.5 * signed_term, 0, 1)`; a robot that closes distance
   from first detection to closest pass now scores below 0.5 instead of
   the previous silent zero. Reason: previous `clip(., 0, 1)` made
   decelerating-while-closing indistinguishable from steady-distance,
   defeating the metric's failure-detection purpose.
7. **Hesitation Rate gates added: yielding mask, inclusive
   goal-reached, displacement gate on reversals.** Section: §Macro:
   Perceived Dexterity → Hesitation Rate. Yielding (stopping for a
   bystander in the forward cone) no longer registers; post-success
   settling no longer registers; brief orientation overshoots no longer
   register as reversals. Reason: previous gates would have made
   Hesitation anti-correlate with deliberate yielding and
   acknowledgement orientation, contradicting the rest of the spec.
8. **Human-Aware Approach `t_approach` redefined as last monotonic
   crossing of `d_personal`, with `t_min_dist` fallback.** Section:
   §Macro: Perceived Social Awareness → Human-Aware Approach. Reason:
   previous "first enters" definition was undefined for the modal
   success case (robot stops at `d_final ≈ 1.3 m`, never enters
   `d_personal = 1.2 m`) and was triggered by legged-base orientation
   wiggles. The fallback covers the modal success case without
   inventing a synthetic value.
9. **Legibility predicate switched from "until episode ends" to
   fractional-coverage form.** Section: §Macro: Impression →
   Legibility. `Leg_i = (1 - t_commit / T) * fraction_inside_cone_post_commit`.
   Reason: the previous global predicate punished legitimate
   goal-direction changes (e.g. swerving around moving bystanders in
   tier 3), causing the moving-tier to systematically score lower for
   exactly the legibility-preserving behavior the cited Mavrogiannis
   2022 supports.

### Applied — Validation plan

10. **Sign-rationale pre-registration added to Weight Matrix v0.**
    Section: §Weight Matrix v0 → Sign Rationale. Every non-zero cell now
    carries a directional prediction and a literature anchor; four cells
    are explicitly flagged as flip-candidates
    (`comfort_aware_path_efficiency → awareness`,
    `hesitation → awareness`, `stability → awareness`,
    `behavioral_naturalness → awareness`). Reason: without
    pre-registration, an elastic-net sign flip on Cohort A becomes a
    silent correction; with it, the flip is a paper-level finding.
11. **Validation Decision Tree added** (ICC bands, per-axis r thresholds,
    drop / split / weakened-headline branches). Section: §Validation
    Plan → Validation Decision Tree. Reason: previous spec only stated
    targets, not what to do when the data missed them. Decision tree
    converts in-flight choices into pre-registered ones.
12. **Multiple-comparisons strategy added.** Section: §Validation Plan →
    Multiple-Comparisons Strategy. Holm-Bonferroni for the 4-axis
    family-wise test, BH-FDR for the 12-cell exploratory tier
    breakdown. Reason: previous power calc treated each axis
    independently at α = 0.05, which inflates the family-wise α for the
    headline claim.
13. **Sample-size and identifiability rewrite.** Section: §Validation
    Plan → Sample Size and Cohort Plan. Episode pool expanded to 30 per
    cohort to put the per-axis fitting N above the underdetermined
    regime; nested-CV alpha selection on Cohort A only; zeroed-feature
    reporting policy specified. Reason: previous "180 pairs per axis"
    figure conflated rating-row count with episode-level analysis unit;
    fitting 16 collinear features against ~12 distinct episodes was
    underdetermined regardless of regularization.
14. **Instrument decision locked to v1 validated subscales for both
    cohorts.** Section: §Validation Plan → Subjective Instrument. The
    v0 anchored Likert is engineering-only and never produces fitting or
    validation data. Reason: previous wording left ambiguous which
    cohort uses which instrument; weights fit on a custom Likert do not
    transfer cleanly to validated subscales.
15. **Stability double-count audit added.** Section: §Validation Plan →
    Stability Double-Count Audit. After Cohort A, regress Impression
    rating on `had_collision` indicator after partialing out the other
    15 features; drop the `stability → impression (1)` cell if the
    partial coefficient is indistinguishable from zero. Reason: the
    spec's claim that raters legitimately double-count collisions was
    asserted, not testable; this turns it into a pre-registered test.
16. **L_optimal moving-tier construction specified.** Section: §Macro:
    Perceived Dexterity → Comfort-Aware Path Efficiency. Bystander
    trajectories are frozen per scenario seed so the comfort-respecting
    optimum is solvable once via a time-windowed planner. Reason:
    previous "precomputed per scenario" wording did not address the
    time-varying obstacle field in tier 3.

### Applied — Strategic positioning

17. **Behavioral Naturalness positioning explicit.** Section: §Macro:
    Impression → Behavioral Naturalness. The benchmark is positioned as
    "morphology-aware core with morphology-agnostic measurement spine":
    only this single metric branches per class; the other 15 are
    class-agnostic. Robots without a declared class report
    `not_applicable` and the macro uses the remaining 4 impression
    sub-indicators. Reason: review surfaced that the metric's
    per-morphology branches contradicted the benchmark's
    morphology-agnostic positioning if not explicitly bounded.

### Applied — Implementation simplification

18. **Library structure flattened.** Section: §Python Library Structure.
    Replaced the 4-subdirectory + aggregation/ subpackage layout with a
    flat 19-file module. A single `aggregation.py` dispatcher replaces
    the four per-axis aggregator files. Reason: the subdirectory split
    added 5 `__init__.py` files and 4 directory traversals for
    navigational convenience only; no caller iterates the subtrees.

### Skipped — telemetry / log-extraction (handled by simulation teammate)

These findings were valid but live outside this spec's scope. They are
the responsibility of the simulation / log-extraction layer owned by the
teammate generating MuJoCo episode logs. The metric library assumes the
log carries:

- `psi_target` (target's facing direction, time-varying when applicable)
- per-step bystander pose stream
- uniform-rate yaw / heading telemetry
- per-step periodic-joint declaration for legged morphologies

Each input is derivable from a MuJoCo simulation; the spec does not
re-specify them here. If a needed input cannot be produced, the
corresponding metric falls back to `not_applicable` per its confidence
behavior.

### FYI / not applied

The doc-review pass also surfaced strategic-framing observations that did
not warrant doc edits: the "characterization-first vs prediction-first"
paper-positioning question (Product F1, F8) is left to the paper writeup
rather than the spec; the validated-only baseline ablation (Product F2)
is recorded as future paper-appendix work alongside the SocNavBench
mapping in §Future Work item 1.

# Social Navigation Metrics

Freeze status: MVP draft approved for implementation; calibration remains
prototype-only until pilot telemetry is reviewed.

Owner approval: Anthor project owner, chat instruction on 2026-05-05 to draft
the metric document and keep backend testing moving.

Scope: v0 social-navigation benchmark with three tiers: empty room, static
bystanders, and moving bystanders. Technical failures are reported separately
from behavioral metrics.

Miro note: the board could not be inspected in this pass because the connector
returned an auth-required error. This draft uses local requirements plus Notion
metric pages.

## Global Conventions

Raw values are computed per valid behavioral episode, then summarized per tier.
Macro scores are equal-weight means of their three sub-indicators when all
three have sufficient evidence. Benchmark aggregate is the equal-weight mean of
available tier macro scores.

Normalization uses `clip((x - bad) / (good - bad), 0, 1)` for indicators where
higher is better, and `clip((bad - x) / (bad - good), 0, 1)` where lower is
better. Threshold constants below are v0 defaults and must be stored in scenario
config so calibration can change values without changing formulas.

Default constants:

- target stop band: `[0.8 m, 1.4 m]`
- target success timeout: `T_max = 120 s`
- personal-space threshold: `d_personal = 1.2 m`
- hard safety floor: `d_hard = 0.45 m`
- near-human threshold: `d_near = 2.0 m`
- acknowledgement cone: `theta_ack = 35 deg`
- acknowledgement response window: `T_ack = 3 s`
- smoothness calibration bounds: `SPARC_bad = -6.0`, `SPARC_good = -2.0`

## Macro: Perceived Dexterity

### Sub-indicator: Task Success Rate

Raw inputs: episode terminal state, final robot pose, target-human pose, stop
time, target stop band, timeout.

Formula: `success_i = 1` when the robot acknowledges the target event, reaches
the target human, and stops with final distance `d_final` inside
`[d_stop_min, d_stop_max]` before `T_max`; otherwise `success_i = 0`.
`TSR = sum(success_i) / N_valid`.

Thresholds: good `TSR = 1.0`; bad `TSR = 0.0`.

Normalization: `R_TSR = 100 * TSR`.

Confidence behavior: insufficient evidence when `N_valid < 3` for a tier.
Technical failures are excluded from `N_valid` and counted in reliability.

Source rationale: local requirement R21; Notion "Task Success Rate" defines
the successes/attempts ratio; requirement R17 defines the two-zone stop rule.

Owner approval: Anthor MVP draft approval, calibration pending.

### Sub-indicator: Task Completion Time

Raw inputs: successful episode completion time `T_i`, timeout `T_max`.

Formula: compute only for successful episodes.
`T_completion = mean(T_i for success_i = 1)`.

Thresholds: good `T_good = 0.35 * T_max`; bad `T_bad = T_max`.

Normalization: `R_time = 100 * clip((T_bad - T_completion) / (T_bad - T_good), 0, 1)`.

Confidence behavior: not applicable when no successful valid episode exists;
insufficient confidence when fewer than 3 valid episodes exist.

Source rationale: local requirement R21; Notion "Task Completion Time" states
that completion time is computed with task success.

Owner approval: Anthor MVP draft approval, calibration pending.

### Sub-indicator: Path Efficiency

Raw inputs: robot trajectory length `L_actual`, shortest collision-free path
length `L_optimal` for the tier map.

Formula: `PE_i = L_optimal / max(L_actual, epsilon)` for successful episodes.
Tier value is `mean(PE_i)`.

Thresholds: good `PE = 1.0`; bad `PE = 0.35`.

Normalization: `R_path = 100 * clip((PE - 0.35) / (1.0 - 0.35), 0, 1)`.

Confidence behavior: not applicable for failed behavioral episodes; insufficient
confidence when fewer than 3 valid episodes exist.

Source rationale: local requirement R21; Notion "Path Efficiency" defines the
ratio between optimal path `Gamma` and actual path `gamma`.

Owner approval: Anthor MVP draft approval, calibration pending.

## Macro: Perceived Safety

### Sub-indicator: Minimum Human-Robot Distance

Raw inputs: robot position `p_r(t)`, every human position `p_hj(t)`.

Formula: `d_min = min_t,j ||p_r(t) - p_hj(t)||`.

Thresholds: good `d_min >= d_personal`; bad `d_min <= d_hard`.

Normalization: `R_min_dist = 100 * clip((d_min - d_hard) / (d_personal - d_hard), 0, 1)`.

Confidence behavior: requires valid robot and human pose streams across the
episode; missing pose telemetry invalidates the episode before metrics.

Source rationale: local requirement R22; Notion "Human-Robot Distance" defines
the minimum Euclidean distance formula; Hall's proxemics work motivates
personal-space thresholds.

Owner approval: Anthor MVP draft approval, calibration pending.

### Sub-indicator: Proxemic Intrusion Time

Raw inputs: `d_j(t) = ||p_r(t) - p_hj(t)||`, personal-space threshold.

Formula: `T_intr = integral_0^T 1(min_j d_j(t) < d_personal) dt`.
Tier value uses intrusion ratio `rho_intr = T_intr / T`.

Thresholds: good `rho_intr = 0`; bad `rho_intr >= 0.25`.

Normalization: `R_prox = 100 * clip((0.25 - rho_intr) / 0.25, 0, 1)`.

Confidence behavior: if no bystanders are present, compute against the target
human only and mark bystander intrusion as not applicable.

Source rationale: local requirement R22; Notion "Personal Space Intrusion Time"
defines the thresholded time integral; HRI proxemics literature treats personal
space as a core signal for social navigation.

Owner approval: Anthor MVP draft approval, calibration pending.

### Sub-indicator: Robot Speed Near Humans

Raw inputs: robot speed `v(t)`, minimum human distance `d(t)`.

Formula: `v_near = integral_0^T v(t) * 1(d(t) < d_near) dt / integral_0^T 1(d(t) < d_near) dt`.

Thresholds: good `v_near <= 0.25 m/s`; bad `v_near >= 1.0 m/s`.

Normalization: `R_speed_near = 100 * clip((1.0 - v_near) / (1.0 - 0.25), 0, 1)`.

Confidence behavior: if the robot never enters the near-human zone, report
`not_applicable` and do not penalize the safety macro.

Source rationale: local requirement R22; Notion "Robot Speed Near the User"
defines the near-distance weighted speed formula.

Owner approval: Anthor MVP draft approval, calibration pending.

## Macro: Perceived Social Awareness

### Sub-indicator: Gesture Response Success

Raw inputs: structured `come_here` task event time, target id, robot motion
start time, target approach direction.

Formula: `GRS_i = 1` when, within `T_ack`, the robot begins moving toward the
target after the event and does not move toward a non-target human first;
otherwise `0`. Tier value is `mean(GRS_i)`.

Thresholds: good `GRS = 1.0`; bad `GRS = 0.0`.

Normalization: `R_gesture = 100 * GRS`.

Confidence behavior: not applicable if the tier contains no `come_here` event;
invalid if event ids cannot be matched to simulated humans.

Source rationale: local requirements R10, R14, and R23 keep raw gesture
recognition out of v0 and evaluate behavior after a structured event.

Owner approval: Anthor MVP draft approval, calibration pending.

### Sub-indicator: Acknowledgement Clarity

Raw inputs: robot forward or sensor-facing direction, target bearing,
acknowledgement cone, response window.

Formula: `ACK_i = 1` if the robot's declared facing direction enters the target
cone `|bearing_error(t)| <= theta_ack` within `T_ack` and before approach;
otherwise `0`.

Thresholds: good `ACK = 1.0`; bad `ACK = 0.0`.

Normalization: `R_ack = 100 * mean(ACK_i)`.

Confidence behavior: low confidence when robot package lacks forward-axis or
sensor-facing metadata; do not infer morphology-specific gestures.

Source rationale: local requirements R16 and R23 define morphology-neutral
acknowledgement through orientation rather than raw visual gestures.

Owner approval: Anthor MVP draft approval, calibration pending.

### Sub-indicator: Human-Aware Approach

Raw inputs: target-human pose, bystander poses, robot trajectory, stop pose.

Formula: combine target progress and bystander respect:
`HA_i = 0.5 * progress_i + 0.5 * bystander_clearance_i`, where
`progress_i = clip((d_start_target - d_final_target) / d_start_target, 0, 1)`
and `bystander_clearance_i = mean_t 1(min_bystander d_b(t) >= d_personal)`.

Thresholds: formula is already in `[0, 1]`; good `HA >= 0.9`; bad `HA <= 0.4`.

Normalization: `R_human_aware = 100 * clip((HA - 0.4) / (0.9 - 0.4), 0, 1)`.

Confidence behavior: in empty-room tier, bystander clearance is neutral and
the indicator uses target progress only.

Source rationale: local requirements R14, R17, and R23 require approach to the
right human while preserving bystander-aware safety.

Owner approval: Anthor MVP draft approval, calibration pending.

## Macro: Impression

### Sub-indicator: Motion Smoothness (SPARC)

Raw inputs: robot base or center-of-mass position `p(t)` sampled at fixed rate.

Formula: compute speed `v(t) = ||dot(p(t))||`, Fourier magnitude spectrum
`V(omega)`, normalized spectrum `V_hat(omega) = V(omega) / V(0)`, then
`SPARC = - integral_0^omega_c sqrt((1/omega_c)^2 + (dV_hat/domega)^2) domega`.

Thresholds: good `SPARC_good = -2.0`; bad `SPARC_bad = -6.0`.

Normalization: `R_smooth = 100 * clip((SPARC - SPARC_bad) / (SPARC_good - SPARC_bad), 0, 1)`.

Confidence behavior: requires uniformly sampled pose telemetry. Resample before
computing or mark insufficient evidence.

Source rationale: Notion "Motion Smoothness (SPARC) - Impression" cites
Balasubramanian et al. 2012/2015 and robot-motion smoothness work.

Owner approval: Anthor MVP draft approval, calibration pending.

### Sub-indicator: Stability / Controlledness

Raw inputs: base orientation, angular velocity, collision/contact flags,
invalid-action flags, and episode fall/instability events.

Formula: `SC_i = 1 - clip((N_instability + N_collision + N_invalid_action) / N_bad, 0, 1)`,
with `N_bad = 3` for v0 smoke calibration.

Thresholds: good `SC = 1.0`; bad `SC = 0.0`.

Normalization: `R_stability = 100 * SC_i`.

Confidence behavior: low confidence for morphologies that cannot expose base
orientation or equivalent stability state; collisions remain valid evidence.

Source rationale: local requirement R24 names stability/controlledness as an
Impression proxy because human-subject ratings are out of scope for v0.

Owner approval: Anthor MVP draft approval, calibration pending.

### Sub-indicator: Morphology-Task Fit

Raw inputs: robot package capability tags, declared locomotion mode, sensor
coverage, action mapping, and scenario-required capabilities.

Formula: `MTF = satisfied_required_capabilities / total_required_capabilities`,
where v0 required capabilities are target approach locomotion, forward/sensor
facing metadata, lidar or equivalent obstacle-distance stream, proprioception,
and controllable joint-target action mapping.

Thresholds: good `MTF = 1.0`; bad `MTF <= 0.4`.

Normalization: `R_morphology = 100 * clip((MTF - 0.4) / (1.0 - 0.4), 0, 1)`.

Confidence behavior: missing package metadata lowers confidence and may lower
score; do not infer hidden hardware capability from behavior alone.

Source rationale: local requirement R24 and the earlier implementation plan
resolve morphology-task fit as a declared-capability rubric, not a learned
human-preference model.

Owner approval: Anthor MVP draft approval, calibration pending.

## Sources

- Local origin requirements:
  `docs/brainstorms/2026-04-29-black-box-robotic-policy-benchmark-requirements.md`.
- Current implementation plan:
  `docs/plans/2026-05-05-001-feat-unified-benchmark-client-server-plan.md`.
- Notion metric pages: Human-Robot Distance, Task Success Rate, Task
  Completion Time, Path Efficiency, Personal Space Intrusion Time, Robot Speed
  Near the User, Interaction Ratio, and Motion Smoothness (SPARC).
- Hall, E. T. (1966). The Hidden Dimension.
- Balasubramanian, S., Melendez-Calderon, A., and Burdet, E. (2012). A robust
  and sensitive metric for quantifying movement smoothness.
- Balasubramanian, S., Melendez-Calderon, A., Roby-Brami, A., and Burdet, E.
  (2015). On the analysis of movement smoothness.
- Human-robot proxemics literature motivates using personal-space distance and
  speed-near-human as social-navigation safety signals.

# Implementation notes for the paper

The paper presents the full metric framework. The released experiment uses
some simpler measurements from navigation traces. This note explains those
choices so the reported scores can be interpreted and reproduced correctly.
The paper PDF, raw data and published result tables are preserved.

## Metric approximations

| Metric | What the experiment actually measures |
|---|---|
| **Task success** | Whether navigation reached its goal. The bridge assumes acknowledgment and supplies a conventional 1.0 m stop distance for successful runs; it does not verify acknowledgment or stopping in front of a person. |
| **Acknowledgment clarity (ACK)** | Initial facing toward the navigation goal, rather than recognition of a caller. The extraction uses a 0.35 radian cone (about 20°), while the full metric specifies 35°. |
| **Human-aware approach** | Progress toward the first NPC's initial position. Clearance and approach-angle components are not supplied. |
| **Comfort-aware path efficiency** | Total traveled distance compared with the straight-line start-to-goal reference. The experiment does not compute a comfort-respecting reference path. |
| **Completion time** | Simulated elapsed time, normalized against the metric default of 120 s. Actual scenario horizons are 28–30 s, so all successful runs score 100 on this feature. |
| **Hesitation and stability** | Hesitation has no explicit labels for yielding or post-goal settling. Stability uses collision counts, without separate fall or invalid-action inputs. |
| **Unscored features** | No come-here or passing events are extracted for gesture response or bystander acknowledgment. The bridge does not supply the joint signal needed for naturalness. Unscored features are omitted and the remaining weights renormalized. |

These are the inputs passed by the [metric bridge](../asimovbm/local_runner/metrics_bridge.py).
The complete feature definitions remain useful as the framework's intended
behavior; the proxy scores above should be interpreted as navigation evidence.

## Experimental and analysis details

- The static scenario contains **block obstacles**. Only the moving-NPC
  scenario supplies human positions. Both policies trigger distance and
  collision caps there; the stricter **collision cap sets safety to 20**.
  Traces end at termination and contain no post-timeout observations.
- The two Policy-B moving-NPC runs start 0.35 m further forward with no start
  delay; the other ten runs use zero offset and a 1 s delay. Comparisons concern
  these recorded conditions, rather than an isolated change of controller.
- The runner emits descriptive scores even below three repetitions. The
  per-scenario table averages two viewpoint runs, not repeated-trial estimates.
- Calibration fits **four policy/viewpoint means**, with slope limited to
  `[0, 3]`, using 50 participants. The other 70 participants rate the same
  policies and scenarios. This tests correspondence across raters, not unseen
  policies. One missing awareness rating is averaged over available items;
  policy comparisons retain 70 participants, while complete viewpoint
  contrasts involving that response use 69.
- **Gap match (91.6)** is `100 − absolute policy-gap error`, floored at zero.
  It is not prediction accuracy. Human comparisons significantly favor A on
  dexterity and impression, matching the uncalibrated benchmark's direction.
  Safety is inconclusive; social-awareness means point in opposite directions
  without a significant human difference. Viewpoint tests are exploratory;
  experience-group differences are associations, not causal effects.

## Videos and scope

The [episode gallery](../artifacts/reconstructed-videos/index.html) renders the
archived joint poses and NPC positions without rerunning the policies.
[Six historical clips](../artifacts/historical-videos/index.html) were recovered
unchanged from Git; their mapping to the original four rated videos remains
unverified. Sources and hashes accompany both galleries. The client–server
system is a design; the experiment uses the implemented local runner.

See the [reproduction guide](README.md) for commands and the
[workflow guide](../docs/paper-workflow.md) for exact fresh-run settings.

# Paper artifact

[The workshop paper](https://openreview.net/forum?id=UNy8Z0IlrK) was presented
at the ICRA 2026 Workshop on Bridging the Gap between Robot Learning and
Human-Robot Interaction. `AsimovBM_ICRA2026.pdf` is the canonical local manuscript. The old LaTeX
workspace was removed because it represented an earlier eight-page draft and
did not reproduce the submitted eleven-page paper.

## Contents

- `assets/`: the six published figures, with the two Figure 5 viewpoints kept
  as separate images.
- `data/human-survey/responses.csv`: the final 120 anonymous survey responses.
  Collection timestamps were removed because they are not used by any paper
  analysis.
- `results/`: compact CSV evidence for the published metric, alignment, paired
  preference, viewpoint, and robot-experience results.
- `analysis/`: the two active notebooks and focused scripts that regenerate
  paper figures or reported statistics.

## Reproduce the analyses

Use Python 3.11 or newer. Create a virtual environment and install the paper
dependencies from the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[paper]'
```

The mixed human/simulation analysis lives in
`analysis/paper_results.ipynb`. It reads the survey responses and the 12
curated validation traces under `../artifacts/local-validation/` and writes
the policy metric table to `results/policy_metric_table.csv`.

Execute that notebook non-interactively from the repository root:

```bash
.venv/bin/jupyter nbconvert --to notebook --execute \
  paper/analysis/paper_results.ipynb \
  --output /tmp/asimovbm-paper-results.ipynb \
  --ExecutePreprocessor.timeout=600
```

Exploratory notebook exports go to the ignored `paper/generated/` directory;
the publication-facing policy table remains in `paper/results/`.

Regenerate the scripted figures and statistics from the repository root:

```bash
.venv/bin/python paper/analysis/generate_metric_weight_matrix.py
.venv/bin/python paper/analysis/generate_paired_policy_ratings.py
.venv/bin/python paper/analysis/generate_profile_alignment.py
.venv/bin/python paper/analysis/generate_robot_experience.py
.venv/bin/python paper/analysis/reproduce_pov_statistics.py
```

Generated figure PDFs overwrite the corresponding publication asset. The
source data and result tables remain plain CSV so results can be inspected
without running a notebook.

## Figure map

| Paper figure | Repository asset |
|---|---|
| Figure 1 — benchmark overview | `assets/fig1_benchmark_overview.pdf` |
| Figure 2 — metric weight matrix | `assets/fig2_metric_weight_matrix.pdf` |
| Figure 3 — paired policy ratings | `assets/fig3_paired_policy_ratings.pdf` |
| Figure 4 — profile alignment | `assets/fig4_profile_alignment.pdf` |
| Figure 5 — camera viewpoints | `assets/fig5_first_person.png`, `assets/fig5_third_person.png` |
| Figure 6 — robot-experience effect | `assets/fig6_robot_experience.pdf` |

## Implementation notes

The short [implementation notes](IMPLEMENTATION_NOTES.md) explain which
measurements approximate the full metric definitions, the calibration setup,
and the scope of the human comparisons. Published data and result tables are
preserved.

## View or regenerate episode videos

Open the [telemetry replay gallery](../artifacts/reconstructed-videos/index.html)
in a browser. It contains twelve episode videos and four policy/viewpoint
compilations, each combining the three scenarios. These are reconstructed
renderings of the released full robot joint poses and obstacle telemetry at
recorded camera settings. They do not rerun the controller or dynamics, and
are not authenticated copies of the videos rated by survey participants.
Frames select the nearest recorded sample from the approximately 50 Hz source
telemetry. The included gallery uses 640×360 at 12 fps; the script defaults to
960×540 at 24 fps for higher-resolution exports.

The [archived video gallery](../artifacts/historical-videos/index.html) also
provides six older clips recovered unchanged from Git history, with their
source commit and checksums. Their mapping to the four rated study videos is
unverified; the [survey provenance notes](../artifacts/survey/README.md) document
the recovery separately from the telemetry renderings.

To regenerate from the repository root, initialize the pinned robot assets,
install the rendering dependencies, and run:

```bash
git submodule update --init --recursive
.venv/bin/python -m pip install -e '.[g1-mujoco]'
.venv/bin/python tools/replay_paper_traces.py --fps 12 --width 640 --height 360
```

The default output is `artifacts/reconstructed-videos/`, including `index.html`,
MP4s and a provenance manifest with SHA-256 hashes of source traces, robot
assets and generated files. Use `--block q1` for a smaller rendering check;
`--fps`, `--width`, `--height` and `--output` control export settings.
Rendering requires an available MuJoCo offscreen graphics backend and FFmpeg;
policy weights are unnecessary for replay. See
[simulation reproduction](../docs/paper-workflow.md#simulation-evidence) for
fresh real-policy runs and the
[survey artifact warning](../artifacts/survey/README.md) for the legacy JSONs.

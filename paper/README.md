# Paper artifact

`AsimovBM_ICRA2026.pdf` is the canonical ICRA 2026 manuscript. The old LaTeX
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

Install the paper dependencies from the repository root:

```bash
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

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
```

The lower-level `python -m g1_slam` entry point still exists for direct
RoboJuDo/MuJoCo exploration, but it is not the canonical Paper HRI validation
launcher.

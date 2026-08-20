# Run Local G1 SLAM Validation

Use the repository-level launcher for paper-submission validation:

```bash
asimovbm-local --robot g1 --iterations 1
```

This loads the three canonical G1 point-to-point configs from
`g1_slam/config/episodes/`, runs them sequentially, records traces, computes
metric outputs, and writes artifacts to `artifacts/local-validation/<run-id>/`.
Use `--robot go2` to run the matching robot-dog point-to-point configs.

Useful variants:

```bash
asimovbm-local --robot g1 --iterations 3 --headless
asimovbm-local --robot g1 --episode g1_point_to_point_open --iterations 1
asimovbm-local --robot go2 --episode go2_point_to_point_static_obstacles --iterations 2 --headless
```

The lower-level `python -m g1_slam` entry point still exists for direct
RoboJuDo/MuJoCo exploration, but it is not the canonical Paper HRI validation
launcher.

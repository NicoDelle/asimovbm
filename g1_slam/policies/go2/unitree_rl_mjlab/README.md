# DiasAiMaster Unitree Go2 Velocity Flat Policy

Place the Go2 velocity policy from
`diasAiMaster/unitree-go2-velocity-flat` here:

```text
policy.onnx
policy.onnx.data
params/deploy.yaml
```

This model is exported as external-data ONNX, so keep `policy.onnx` and
`policy.onnx.data` together in this directory. `params/deploy.yaml` is useful
for checking the model's original observation/action deployment settings.

Download the real files with:

```bash
huggingface-cli download diasAiMaster/unitree-go2-velocity-flat \
  policy.onnx policy.onnx.data params/deploy.yaml \
  --local-dir g1_slam/policies/go2/unitree_rl_mjlab
```

If `policy.onnx` is about 130 bytes and starts with
`version https://git-lfs.github.com/spec/v1`, it is only a Git LFS pointer and
must be re-downloaded.

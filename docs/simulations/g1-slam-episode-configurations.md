# G1 And Go2 Point-To-Point Episode Configurations

The checked-in `g1_slam` episode catalog contains only the point-to-point
scenarios:

- `g1_point_to_point_open`
- `g1_point_to_point_static_obstacles`
- `g1_point_to_point_dynamic_npcs`
- `go2_point_to_point_open`
- `go2_point_to_point_static_obstacles`
- `go2_point_to_point_dynamic_npcs`

The G1 configs use RoboJuDo locomotion. The Go2 configs are the robot-dog
counterparts for the same scenario types and use the Go2 ONNX velocity policy.

Each config sets the robot start pose, goal, world bounds, obstacle layout,
controller limits, locomotion mode, and fixed viewer framing. Each one also
defines two named camera views:

- `arrival`: framed from the goal side.
- `bystander`: framed from the side.

## Run From The G1 SLAM Package

```bash
cd g1_slam
conda activate asimovbm
```

Run a G1 humanoid episode:

```bash
PYTHONPATH=src python3 -m g1_slam \
  --config config/episodes/g1_point_to_point_open.json \
  --camera-view arrival \
  --render
```

Run the same scenario type with the Go2 robot dog:

```bash
PYTHONPATH=src python3 -m g1_slam \
  --config config/episodes/go2_point_to_point_open.json \
  --mujoco \
  --robot official_go2 \
  --camera-view arrival \
  --render
```

## G1 Policy Variants

G1 point-to-point episodes default to `g1_asap_loco`. Use
`--robojudo-config g1` to run the same episode with the Unitree G1 RoboJuDo
policy config:

```bash
PYTHONPATH=src python3 -m g1_slam \
  --config config/episodes/g1_point_to_point_static_obstacles.json \
  --robojudo-config g1 \
  --camera-view bystander \
  --render
```

## Go2 Policy Assets

The Go2 configs are tuned for the Hugging Face model
`diasAiMaster/unitree-go2-velocity-flat`. The expected files live under:

```text
policies/go2/unitree_rl_mjlab/policy.onnx
policies/go2/unitree_rl_mjlab/policy.onnx.data
policies/go2/unitree_rl_mjlab/params/deploy.yaml
```

Download them from inside `g1_slam/`:

```bash
huggingface-cli download diasAiMaster/unitree-go2-velocity-flat \
  policy.onnx policy.onnx.data params/deploy.yaml \
  --local-dir policies/go2/unitree_rl_mjlab
```

The downloaded `policy.onnx` should be the binary model, not a Git LFS pointer.

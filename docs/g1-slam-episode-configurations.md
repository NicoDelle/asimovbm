# G1 And Go2 SLAM Episode Configurations

These files define six MuJoCo episodes with the same SLAM navigation loop:

- Three G1 humanoid episodes using RoboJuDo locomotion.
- Three Unitree Go2 quadruped episodes using the official `unitree_mujoco`
  Go2 model and an external ONNX velocity policy.

Each configuration sets the robot start pose, goal, world bounds, obstacle
layout, controller limits, locomotion mode, and fixed viewer framing.
The Go2 MuJoCo viewer opens without the left/right option panels so the window
shows only the fixed scene view.

## Prerequisites

Run the commands from the G1 SLAM package root:

```bash
cd ~/palingenesys/asimovbm/g1_slam
conda activate asimovbm
```

For the G1 episodes, RoboJuDo and its `mujoco_viewer` dependency must already
be installed as described in `docs/run-g1-slam-episode.md`.

For the Go2 episodes, RoboJuDo is not used. The policy profile is tuned for the
Hugging Face model `diasAiMaster/unitree-go2-velocity-flat`, trained with
Unitree's `unitree_rl_mjlab` Go2 velocity task. Download the model files into:

```text
policies/go2/unitree_rl_mjlab/policy.onnx
policies/go2/unitree_rl_mjlab/policy.onnx.data
policies/go2/unitree_rl_mjlab/params/deploy.yaml
```

Use:

```bash
huggingface-cli download diasAiMaster/unitree-go2-velocity-flat \
  policy.onnx policy.onnx.data params/deploy.yaml \
  --local-dir policies/go2/unitree_rl_mjlab
```

The downloaded `policy.onnx` should be a binary file, not a 130-byte Git LFS
pointer. The runner sends the SLAM controller's `(linear_velocity, yaw_rate)`
command into this model's observation layout:

```text
base_ang_vel, projected_gravity, velocity_commands,
joint_pos_rel, joint_vel_rel, last_action
```

This model was published without `gait_phase` and with action scale `0.5`, so
the Go2 episode configs use `observation_profile:
"dias_ai_master_go2_velocity_flat"`, `observation_size: 45`, and
`action_scale: 0.5`.

## G1 Episodes

### 1. Open Lateral Motion

Config file:

```text
config/episodes/g1_lateral_open.json
```

Run:

```bash
python3 -m g1_slam --config config/episodes/g1_lateral_open.json --render
```

This episode keeps the world empty: no static red blocks and no dynamic blue
cylinders. The robot walks from one side of the scene to the other while the
viewer stays fixed and the final green goal marker remains visible.

### 2. Lateral Motion With Static Obstacles And NPCs

Config file:

```text
config/episodes/g1_lateral_static_dynamic_obstacles.json
```

Run:

```bash
python3 -m g1_slam --config config/episodes/g1_lateral_static_dynamic_obstacles.json --render
```

This shorter episode includes static red blocks plus three lightweight
pedestrian NPCs without turning the run into a long maze:

- Two static red box obstacles are declared in the config `world.obstacles` list.
- Three moving NPCs are enabled through `dynamic_obstacles.mode: "npcs"` and
  `dynamic_obstacles.count`.
- The NPCs use the `social_patrol` policy, a deterministic low-cost patrol that
  validates its full path against the static obstacle map before the scene is
  generated.

The SLAM scan world is updated with the moving NPCs over time, and the
RoboJuDo MuJoCo scene renders the same red obstacles and NPC actors. The
fixed camera keeps the short route visible without drawing a trajectory trace.

### 3. Robot Approaching The User

Config file:

```text
config/episodes/g1_approach_user.json
```

Run:

```bash
python3 -m g1_slam --config config/episodes/g1_approach_user.json --render
```

This episode treats the laptop viewer as the user position. The robot starts a
few meters away and approaches a goal that stops it at a comfortable distance
instead of walking all the way into the camera. The camera stays fixed so the
robot approach and final marker stay easy to see.

## Go2 Episodes

### 4. Go2 Open Lateral Motion

Config file:

```text
config/episodes/go2_lateral_open.json
```

Run:

```bash
python3 -m g1_slam \
  --config config/episodes/go2_lateral_open.json \
  --mujoco \
  --robot official_go2 \
  --render
```

This mirrors the open G1 lateral episode, but uses the Unitree Go2 quadruped
MJCF and `locomotion.mode="policy"` with the `dias_ai_master_go2_velocity_flat`
observation profile.

### 5. Go2 Lateral Motion With Static Obstacles And NPCs

Config file:

```text
config/episodes/go2_lateral_static_dynamic_obstacles.json
```

Run:

```bash
python3 -m g1_slam \
  --config config/episodes/go2_lateral_static_dynamic_obstacles.json \
  --mujoco \
  --robot official_go2 \
  --render
```

This mirrors the mixed-obstacle G1 episode. Static red boxes are baked into the
generated Go2 navigation scene, while the NPCs are generated as mocap bodies
and moved over time in both MuJoCo and the SLAM lidar world.

### 6. Go2 Approaching The User

Config file:

```text
config/episodes/go2_approach_user.json
```

Run:

```bash
python3 -m g1_slam \
  --config config/episodes/go2_approach_user.json \
  --mujoco \
  --robot official_go2 \
  --render
```

This mirrors the G1 user-approach episode with lower Go2 camera framing and
quadruped controller speed limits.

## Optional Overrides

You can still override the config from the command line:

```bash
python3 -m g1_slam \
  --config config/episodes/g1_lateral_static_dynamic_obstacles.json \
  --dynamic-cylinder-seed 42 \
  --render
```

To swap the same episode back to blue cylinders:

```bash
python3 -m g1_slam \
  --config config/episodes/g1_lateral_static_dynamic_obstacles.json \
  --dynamic-obstacle-mode blue_cylinders \
  --dynamic-obstacle-count 3 \
  --render
```

To force NPCs from a legacy cylinder config:

```bash
python3 -m g1_slam \
  --config config/episodes/g1_lateral_static_dynamic_obstacles.json \
  --dynamic-obstacle-mode npcs \
  --dynamic-obstacle-count 2 \
  --npc-policy social_patrol \
  --render
```

For a different endpoint:

```bash
python3 -m g1_slam \
  --config config/episodes/g1_approach_user.json \
  --goal -1.2 0.5 \
  --render
```

For a different Go2 policy:

```bash
python3 -m g1_slam \
  --config config/episodes/go2_lateral_open.json \
  --mujoco \
  --robot official_go2 \
  --policy-path policies/go2/unitree_rl_mjlab/my_policy.onnx \
  --render
```

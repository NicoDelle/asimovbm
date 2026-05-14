# G1 And Go2 SLAM Episode Configurations

These files define twelve MuJoCo episodes with the same SLAM navigation loop:

- Six G1 humanoid episodes using RoboJuDo locomotion.
- Six Unitree Go2 quadruped episodes using the official `unitree_mujoco`
  Go2 model and an external ONNX velocity policy.

Each configuration sets the robot start pose, goal, world bounds, obstacle
layout, controller limits, locomotion mode, and fixed viewer framing.
The Go2 MuJoCo viewer opens without the left/right option panels so the window
shows only the fixed scene view.

The generated MuJoCo scenes use a recording-oriented visual environment: a
solid matte floor, a sky gradient, softer multi-directional lighting, and
subtle NPC shadows. These visual elements do not change the SLAM world or
collision planning; they are there to make screen recordings feel less like a
debug scene while keeping the camera view open.

## Prerequisites

Run the commands from the G1 SLAM package root:

```bash
cd ~/palingenesys/asimovbm/g1_slam
conda activate asimovbm
```

For the G1 episodes, RoboJuDo and its `mujoco_viewer` dependency must already
be installed as described in `run-g1-slam-episode.md`.

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

## Camera Views

Each episode can be rendered with a named camera view from the episode JSON:

- `--camera-view arrival` frames the viewer from the goal side, looking back at
  the route so the robot appears to approach.
- `--camera-view bystander` frames the route from the side so the viewer sees
  the robot move from point A to point B.

If no view is passed, `--camera-view config` uses `visualization.camera`.
The `arrival` and `bystander` values are stored under
`visualization.camera_views`, so each episode can tune its own camera positions
without changing Python code.

## G1 Episodes

The three point-to-point G1 episode JSON files set `controller.start_delay_s:
1.0`, so the viewer opens with a one-second hold before navigation commands
move the robot forward. The local `asimovbm-local` wrapper applies a
survey-timing override for `g1_point_to_point_dynamic_npcs` with policy B
(`g1_robojudo_asap` / RoboJuDo `g1_asap_loco`): start delay `0.0`, matching the
recording where ASAP walks straight away. That same local-run pairing also
moves the start pose by `+0.35 m` on the x-axis, placing the robot slightly
farther forward in the dynamic-NPC episode. Use `--start-x-offset <meters>` to
tune that forward nudge, `--route-y-offset <meters>` to tune a side-lane nudge,
and `--start-delay <seconds>` to tune the hold time manually.

### 1. Point-To-Point Motion Without Obstacles

Config file:

```text
config/episodes/g1_point_to_point_open.json
```

Run:

```bash
python3 -m g1_slam --config config/episodes/g1_point_to_point_open.json --render
```

This episode moves the G1 from point A to point B in an empty world. It has no
static obstacles and no dynamic obstacles. The navigation floor spans a larger
`16m x 10m` world.

### 2. Point-To-Point Motion With Static Obstacles

Config file:

```text
config/episodes/g1_point_to_point_static_obstacles.json
```

Run:

```bash
python3 -m g1_slam --config config/episodes/g1_point_to_point_static_obstacles.json --render
```

This episode keeps the same point A to point B route, but places two static red
block obstacles in the larger world so SLAM has to route around them.

### 3. Point-To-Point Motion With Dynamic NPCs

Config file:

```text
config/episodes/g1_point_to_point_dynamic_npcs.json
```

Run:

```bash
python3 -m g1_slam --config config/episodes/g1_point_to_point_dynamic_npcs.json --render
```

This episode keeps the static world empty and enables two moving pedestrian
NPCs through `dynamic_obstacles.mode: "npcs"` and the `social_patrol` policy.
The NPC centers are declared in the JSON at one-third and two-thirds of the
current start-to-goal distance.

### 4. Open Lateral Motion

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

### 5. Lateral Motion With Static Obstacles And NPCs

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

### 6. Robot Approaching The User

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

### 7. Go2 Point-To-Point Motion Without Obstacles

Config file:

```text
config/episodes/go2_point_to_point_open.json
```

Run:

```bash
python3 -m g1_slam \
  --config config/episodes/go2_point_to_point_open.json \
  --mujoco \
  --robot official_go2 \
  --render
```

This mirrors the G1 point-to-point open episode with the Go2 policy locomotion
profile and the same larger `16m x 10m` floor.

### 8. Go2 Point-To-Point Motion With Static Obstacles

Config file:

```text
config/episodes/go2_point_to_point_static_obstacles.json
```

Run:

```bash
python3 -m g1_slam \
  --config config/episodes/go2_point_to_point_static_obstacles.json \
  --mujoco \
  --robot official_go2 \
  --render
```

This mirrors the G1 static-obstacle point-to-point episode with two static red
blocks and no dynamic obstacles.

### 9. Go2 Point-To-Point Motion With Dynamic NPCs

Config file:

```text
config/episodes/go2_point_to_point_dynamic_npcs.json
```

Run:

```bash
python3 -m g1_slam \
  --config config/episodes/go2_point_to_point_dynamic_npcs.json \
  --mujoco \
  --robot official_go2 \
  --render
```

This mirrors the G1 dynamic point-to-point episode using three moving
pedestrian NPCs and no static obstacles.

### 10. Go2 Open Lateral Motion

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

### 11. Go2 Lateral Motion With Static Obstacles And NPCs

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

### 12. Go2 Approaching The User

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

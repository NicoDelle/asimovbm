# Run Point-To-Point Episodes And Swap Policies

This guide covers the six new point-to-point episodes:

- G1 humanoid with RoboJuDo locomotion.
- Go2 quadruped with the ONNX velocity policy path.
- Three environment variants for each robot: open floor, static obstacles, and
  dynamic NPC pedestrians.

Run every command from the G1 SLAM package root:

```bash
cd ~/palingenesys/asimovbm/g1_slam
conda activate asimovbm
```

## Camera Views

Every command below can use one of the two named recording views from the
episode JSON:

- `--camera-view arrival`: the camera is framed from the goal side, looking back
  toward the robot so the robot appears to approach the viewer.
- `--camera-view bystander`: the camera watches from the side as the robot moves
  from point A to point B.

The default `--camera-view config` keeps `visualization.camera`. The named
views use `visualization.camera_views.arrival` and
`visualization.camera_views.bystander`, so camera positions can be tuned per
episode without code changes.

Example:

```bash
python3 -m g1_slam \
  --config config/episodes/g1_point_to_point_open.json \
  --camera-view arrival \
  --render
```

## G1 Point-To-Point Episodes

G1 episodes use `locomotion.robojudo_config` from the episode JSON. The default
for these point-to-point episodes is `g1_asap_loco`. Use
`--robojudo-config g1` to run the same episode with the Unitree G1 RoboJuDo
policy config.

Each episode JSON sets `controller.start_delay_s` to `1.0`, so the simulation
starts, holds the robot in place for one second, and then begins sending
navigation commands.

For the humanoid, run the full 12-command sweep when you want every combination
of the three environments, two RoboJuDo configs, and two named camera views:

- Environments: open floor, static obstacles, dynamic NPCs.
- RoboJuDo configs: `g1_asap_loco`, `g1`.
- Camera views: `arrival`, `bystander`.

### Open Floor

Open floor, `g1_asap_loco`, arrival view:

```bash
python3 -m g1_slam \
  --config config/episodes/g1_point_to_point_open.json \
  --robojudo-config g1_asap_loco \
  --camera-view arrival \
  --render
```

Open floor, `g1_asap_loco`, bystander view:

```bash
python3 -m g1_slam \
  --config config/episodes/g1_point_to_point_open.json \
  --robojudo-config g1_asap_loco \
  --camera-view bystander \
  --render
```

Open floor, `g1`, arrival view:

```bash
python3 -m g1_slam \
  --config config/episodes/g1_point_to_point_open.json \
  --robojudo-config g1 \
  --camera-view arrival \
  --render
```

Open floor, `g1`, bystander view:

```bash
python3 -m g1_slam \
  --config config/episodes/g1_point_to_point_open.json \
  --robojudo-config g1 \
  --camera-view bystander \
  --render
```

### Static Obstacles

Static obstacles, `g1_asap_loco`, arrival view:

```bash
python3 -m g1_slam \
  --config config/episodes/g1_point_to_point_static_obstacles.json \
  --robojudo-config g1_asap_loco \
  --camera-view arrival \
  --render
```

Static obstacles, `g1_asap_loco`, bystander view:

```bash
python3 -m g1_slam \
  --config config/episodes/g1_point_to_point_static_obstacles.json \
  --robojudo-config g1_asap_loco \
  --camera-view bystander \
  --render
```

Static obstacles, `g1`, arrival view:

```bash
python3 -m g1_slam \
  --config config/episodes/g1_point_to_point_static_obstacles.json \
  --robojudo-config g1 \
  --camera-view arrival \
  --render
```

Static obstacles, `g1`, bystander view:

```bash
python3 -m g1_slam \
  --config config/episodes/g1_point_to_point_static_obstacles.json \
  --robojudo-config g1 \
  --camera-view bystander \
  --render
```

### Dynamic NPCs

Dynamic obstacles, `g1_asap_loco`, arrival view:

```bash
python3 -m g1_slam \
  --config config/episodes/g1_point_to_point_dynamic_npcs.json \
  --robojudo-config g1_asap_loco \
  --camera-view arrival \
  --render
```

Dynamic obstacles, `g1_asap_loco`, bystander view:

```bash
python3 -m g1_slam \
  --config config/episodes/g1_point_to_point_dynamic_npcs.json \
  --robojudo-config g1_asap_loco \
  --camera-view bystander \
  --render
```

Dynamic obstacles, `g1`, arrival view:

```bash
python3 -m g1_slam \
  --config config/episodes/g1_point_to_point_dynamic_npcs.json \
  --robojudo-config g1 \
  --camera-view arrival \
  --render
```

Dynamic obstacles, `g1`, bystander view:

```bash
python3 -m g1_slam \
  --config config/episodes/g1_point_to_point_dynamic_npcs.json \
  --robojudo-config g1 \
  --camera-view bystander \
  --render
```

## Go2 Point-To-Point Episodes

Open floor, no obstacles:

```bash
python3 -m g1_slam \
  --config config/episodes/go2_point_to_point_open.json \
  --mujoco \
  --robot official_go2 \
  --camera-view bystander \
  --render
```

Static obstacles, two red blocks:

```bash
python3 -m g1_slam \
  --config config/episodes/go2_point_to_point_static_obstacles.json \
  --mujoco \
  --robot official_go2 \
  --camera-view bystander \
  --render
```

Dynamic obstacles, three pedestrian NPCs:

```bash
python3 -m g1_slam \
  --config config/episodes/go2_point_to_point_dynamic_npcs.json \
  --mujoco \
  --robot official_go2 \
  --camera-view bystander \
  --render
```

## Use Another Go2 Policy

If the new policy has the same observation layout as
`dias_ai_master_go2_velocity_flat`, place the ONNX files under a new policy
directory and override the path:

```text
policies/go2/my_policy/policy.onnx
policies/go2/my_policy/policy.onnx.data
```

```bash
python3 -m g1_slam \
  --config config/episodes/go2_point_to_point_open.json \
  --mujoco \
  --robot official_go2 \
  --policy-path policies/go2/my_policy/policy.onnx \
  --render
```

To make that policy permanent for an episode, edit the episode JSON:

```json
"locomotion": {
  "mode": "policy",
  "policy_path": "policies/go2/my_policy/policy.onnx",
  "observation_size": 45,
  "observation_profile": "dias_ai_master_go2_velocity_flat",
  "action_scale": 0.5,
  "kp": 50.0,
  "kd": 3.5
}
```

If the policy uses a different observation vector, action scale, joint order, or
normalization contract, add a new observation profile in
`src/g1_slam/locomotion.py` instead of only changing `policy_path`.

Typical code changes for a new Go2 policy profile:

1. Add a new profile constant near the existing Go2 profile constants.
2. Extend the policy binding selection if the action order or controlled joints
   differ.
3. Add an observation builder branch for the new profile.
4. Set `observation_profile`, `observation_size`, and `action_scale` in the
   episode JSON.
5. Add or update tests in `g1_slam/tests/test_navigation.py`.

The runner rejects missing ONNX files and Git LFS pointer files. If the model
uses external ONNX data, keep `policy.onnx.data` next to `policy.onnx`.

## Use Another G1 RoboJuDo Policy

G1 episodes use RoboJuDo rather than the Go2 ONNX policy runner. For G1, changing
`--policy-path` is not the policy swap path. The persistent episode default is
`locomotion.robojudo_config`; the CLI override is `--robojudo-config`.

```json
"locomotion": {
  "mode": "robojudo",
  "policy_path": "policies/g1/policy.onnx",
  "robojudo_config": "g1_asap_loco",
  "observation_size": null,
  "action_scale": 0.25,
  "kp": 35.0,
  "kd": 1.0
}
```

Use `--robojudo-config g1` when you want to test the same episode without
editing JSON.

To integrate a new G1 RoboJuDo policy:

1. Add the policy model and RoboJuDo config under
   `g1_slam/third_party/RoboJuDo`.
2. Confirm RoboJuDo can instantiate that config independently.
3. Run `python3 -m g1_slam` with `--robojudo-config <new_config_name>`.
4. If the new policy expects different command limits, update the episode
   `controller.max_linear_speed` and `controller.max_yaw_rate` values.

## Useful Overrides

Run fewer steps while testing:

```bash
python3 -m g1_slam \
  --config config/episodes/go2_point_to_point_dynamic_npcs.json \
  --mujoco \
  --robot official_go2 \
  --steps 300 \
  --render
```

Change the NPC count without editing JSON:

```bash
python3 -m g1_slam \
  --config config/episodes/g1_point_to_point_dynamic_npcs.json \
  --dynamic-obstacle-count 2 \
  --render
```

Move the goal for a quick route experiment:

```bash
python3 -m g1_slam \
  --config config/episodes/g1_point_to_point_open.json \
  --goal 3.0 0.5 \
  --render
```

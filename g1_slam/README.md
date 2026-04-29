# G1 SLAM in MuJoCo

2D SLAM and navigation baseline for a Unitree G1-like humanoid. The goal is to move the robot from a start point to a target while building an occupancy map and avoiding obstacles.

The implementation is split into two layers:

- `g1_slam`: SLAM, simulated 2D lidar, A* planner, and path-following controller. It does not depend on MuJoCo or NumPy.
- `assets/g1_kinematic.xml`: MuJoCo scene with a simplified kinematic G1 humanoid. It is useful for visualizing navigation and testing the architecture before connecting a full dynamic controller.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## Run Without MuJoCo

The pure Python mode is useful for validating SLAM, planning, and obstacle avoidance:

```bash
PYTHONPATH=src python3 -m g1_slam --out runs
```

It generates:

- `runs/map.pgm`: occupancy map.
- `runs/path.csv`: trajectory followed by the robot.

## Run With MuJoCo

With `mujoco` installed:

```bash
PYTHONPATH=src python3 -m g1_slam --mujoco --render
```

Headless:

```bash
PYTHONPATH=src python3 -m g1_slam --mujoco
```

The default MuJoCo robot is the simplified kinematic model:

```bash
PYTHONPATH=src python3 -m g1_slam --mujoco --robot kinematic --render
```

To use the official Unitree G1 model, clone the G1 assets first:

```bash
mkdir -p third_party
git clone --depth 1 --filter=blob:none --sparse https://github.com/unitreerobotics/unitree_mujoco.git third_party/unitree_mujoco
cd third_party/unitree_mujoco
git sparse-checkout set unitree_robots/g1
cd -
```

Then run:

```bash
PYTHONPATH=src python3 -m g1_slam --mujoco --robot official_g1 --render
```

For `official_g1`, the runner generates a local navigation scene next to the official G1 XML so the `meshes/` directory resolves correctly. At this stage the official robot is moved kinematically for visualization; dynamic humanoid locomotion is the next layer.

## Policy Locomotion

The navigation layer can drive the official G1 through an ONNX locomotion policy:

```bash
PYTHONPATH=src python3 -m g1_slam --mujoco --robot official_g1 --locomotion policy --render
```

The policy path and low-level PD gains are configured in `config/navigation.json`:

```json
"locomotion": {
  "mode": "kinematic",
  "policy_path": "policies/g1/policy.onnx",
  "observation_size": null,
  "action_scale": 0.25,
  "kp": 35.0,
  "kd": 1.0
}
```

Use `"mode": "policy"` or pass `--locomotion policy` from the command line. The ONNX policy is expected to receive a single observation tensor and return normalized joint actions for the G1 actuators. The runner converts those actions to joint torques with:

```text
torque = kp * (target_joint_angle - joint_angle) - kd * joint_velocity
target_joint_angle = default_angle + action_scale * policy_action
```

The current observation is intentionally generic: velocity command, placeholder base orientation terms, joint position offsets, joint velocities, and previous action. Real policies often require an exact observation layout, so update `src/g1_slam/locomotion.py` to match the policy you use.

## RoboJuDo Locomotion

RoboJuDo can also run as the MuJoCo locomotion backend, without ROS:

```bash
PYTHONPATH=src python -m g1_slam --locomotion robojudo
```

By default this uses:

```text
third_party/RoboJuDo
g1_asap_loco
```

You can override them:

```bash
PYTHONPATH=src python -m g1_slam \
  --locomotion robojudo \
  --robojudo-repo third_party/RoboJuDo \
  --robojudo-config g1_asap_loco
```

This mode lets RoboJuDo own the MuJoCo simulation and replaces its joystick controller with a virtual joystick fed by the SLAM navigation command.

## Navigation Config

The start pose, goal position, and default number of steps live in:

```text
config/navigation.json
```

Example:

```json
{
  "start": {
    "x": -4.2,
    "y": -3.2,
    "yaw": 0.0
  },
  "goal": {
    "x": -4.2,
    "y": -1.0
  },
  "steps": 900,
  "controller": {
    "lookahead": 0.55,
    "waypoint_tolerance": 0.25,
    "goal_tolerance": 0.28,
    "max_linear_speed": 0.65,
    "max_yaw_rate": 1.4
  }
}
```

When running with MuJoCo, the green goal marker is moved at runtime using this config. The `goal` position inside `assets/g1_kinematic.xml` is only a fallback for loading the XML directly.

You can also use another config file:

```bash
PYTHONPATH=src python3 -m g1_slam --config config/my_navigation.json --mujoco --render
```

Command-line values override the config:

```bash
PYTHONPATH=src python3 -m g1_slam --start -4.0 -3.0 0.0 --goal 5.5 2.5 --steps 1200
```

## Structure

- `config/navigation.json`: default start pose, goal, and number of simulation steps.
- `src/g1_slam/config.py`: navigation config loader.
- `src/g1_slam/geometry.py`: poses and geometry utilities.
- `src/g1_slam/world.py`: 2D world and rectangular obstacles.
- `src/g1_slam/lidar.py`: 2D lidar using ray marching.
- `src/g1_slam/mapping.py`: log-odds occupancy grid.
- `src/g1_slam/planner.py`: A* with obstacle inflation.
- `src/g1_slam/controller.py`: waypoint following.
- `src/g1_slam/simulation.py`: SLAM + planning + control loop.
- `src/g1_slam/mujoco_runner.py`: optional MuJoCo visualization backend.

## Next Step Toward The Real Unitree G1

This baseline provides the perception and navigation layer. For a fully dynamic G1, replace the kinematic humanoid with the official robot MJCF and connect the controller command `(v, yaw_rate)` to a biped locomotion controller, such as MPC/WBC or a trained walking policy.

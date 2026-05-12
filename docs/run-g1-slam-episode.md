# Run a G1 SLAM Episode

This page is for the sim-native G1 episode path: the real RoboJuDo-backed
MuJoCo simulation, run sequentially from the `g1_slam/config/episodes` JSON
configs, with JSON traces written for the metrics consumer.

This guide is intentionally beginner-friendly. It assumes you want to open the
G1 RoboJuDo simulation, run SLAM/navigation, and watch the humanoid react to
dynamic blue cylinders.

## 1. Open a Terminal

Go to the repository:

```bash
cd /home/nico/Code/asimovbm
```

Use the repo virtualenv for every Python command in this repository.

## 2. Install the RoboJuDo Viewer Dependency

RoboJuDo needs an optional viewer package named `mujoco_viewer`.

Run this once:

```bash
cd g1_slam/third_party/RoboJuDo
/home/nico/Code/asimovbm/.venv/bin/python submodule_install.py mujoco_viewer
```

Go back to the repository root:

```bash
cd /home/nico/Code/asimovbm
```

Quick check:

```bash
.venv/bin/python -c "import mujoco_viewer; print('mujoco_viewer OK')"
```

If this prints `mujoco_viewer OK`, the viewer dependency is installed.

## 3. Run the G1 Episode Suite Sequentially

Use this command:

```bash
.venv/bin/asimovbm-server sim-episodes \
  --episode-robot g1 \
  --render \
  --trace-root artifacts/sim-traces/g1
```

What this does:

- Loads the G1 episode configs from `g1_slam/config/episodes`.
- Runs them sequentially for easier visualization.
- Uses the real RoboJuDo-backed G1 loop instead of the server-local marker sim.
- Writes per-episode traces and `episode_suite_summary.json` under the trace root.

## 4. Run Without the Viewer

If you only want the episode to execute without opening a window:

```bash
.venv/bin/asimovbm-server sim-episodes \
  --episode-robot g1 \
  --trace-root artifacts/sim-traces/g1
```

## 5. Run One Episode

Use either the full config stem or the suffix without `g1_`:

```bash
.venv/bin/asimovbm-server sim-episodes \
  --episode-robot g1 \
  --episodes lateral_static_dynamic_obstacles \
  --render \
  --trace-root artifacts/sim-traces/g1
```

## 6. Run the Older Single-Config Demo

The older one-off entry point still exists for quick debugging:

```bash
PYTHONPATH=g1_slam/src .venv/bin/python -m g1_slam \
  --config g1_slam/config/episodes/g1_lateral_static_dynamic_obstacles.json \
  --render \
  --trace-root artifacts/sim-traces/g1
```

## 7. Override Start, Goal, or Duration

Start position:

```bash
PYTHONPATH=g1_slam/src .venv/bin/python -m g1_slam --locomotion robojudo --dynamic-blue-cylinders --start -8 0 0 --render
```

Farther goal:

```bash
PYTHONPATH=g1_slam/src .venv/bin/python -m g1_slam --locomotion robojudo --dynamic-blue-cylinders --goal 14 0 --render
```

More steps:

```bash
PYTHONPATH=g1_slam/src .venv/bin/python -m g1_slam --locomotion robojudo --dynamic-blue-cylinders --steps 2500 --render
```

You can combine them:

```bash
PYTHONPATH=g1_slam/src .venv/bin/python -m g1_slam \
  --locomotion robojudo \
  --dynamic-blue-cylinders \
  --start -8 0 0 \
  --goal 14 0 \
  --steps 2500 \
  --render
```

## 8. Trace Output

Each episode writes `<episode-id>-trace.json` with schema
`asimovbm.sim_trace.v1`. The metrics consumer should read:

- `episode_id`, `robot_id`, `policy_id`, `status`, `reached_goal`
- `goal`, `final_pose`, `step_count`
- `steps[]`, containing `time_s`, `robot_pose`, `command`,
  `distance_to_goal`, `entities`, and `path`

The suite also writes `episode_suite_summary.json`.

## 9. Common Problems

### `No module named 'mujoco_viewer'`

Install the RoboJuDo viewer dependency:

```bash
cd /home/nico/Code/asimovbm/g1_slam/third_party/RoboJuDo
/home/nico/Code/asimovbm/.venv/bin/python submodule_install.py mujoco_viewer
```

### `Failed to open display :0`

The viewer needs a graphical desktop session. Run the command from your normal
desktop terminal, not from a headless SSH session or an environment without X11.

### The Robot Falls

That usually means the policy/controller is not fully active yet, the wrong
RoboJuDo config is being used, or the simulation is starting before the policy
has stabilized. First try the default command in this guide before changing
start, goal, or step count.

## 10. Quick Smoke Test

Before opening the full viewer, check that the command-line entry point works:

```bash
.venv/bin/asimovbm-server sim-episodes --help
```

You should see options including:

- `--run-episodes`
- `--episode-robot`
- `--episodes`
- `--trace-root`
- `--render`

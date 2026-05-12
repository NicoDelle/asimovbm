# Run a G1 SLAM Episode

This guide is intentionally beginner-friendly. It assumes you want to open the
G1 RoboJuDo simulation, run SLAM/navigation, and watch the humanoid react to
dynamic blue cylinders.

For the three reusable episode configurations, see
`docs/g1-slam-episode-configurations.md`.

## 1. Open a Terminal

Go to the repository:

```bash
cd ~/palingenesys/asimovbm
```

Activate the Python environment:

```bash
conda activate asimovbm
```

## 2. Install the RoboJuDo Viewer Dependency

RoboJuDo needs an optional viewer package named `mujoco_viewer`.

Run this once:

```bash
cd g1_slam/third_party/RoboJuDo
python3 submodule_install.py mujoco_viewer
```

Go back to the G1 SLAM package:

```bash
cd ~/palingenesys/asimovbm/g1_slam
```

Quick check:

```bash
python3 -c "import mujoco_viewer; print('mujoco_viewer OK')"
```

If this prints `mujoco_viewer OK`, the viewer dependency is installed.

## 3. Run the Default Dynamic Episode

Use this command:

```bash
python3 -m g1_slam --locomotion robojudo --dynamic-blue-cylinders --render
```

What this does:

- Uses the RoboJuDo locomotion policy.
- Opens the MuJoCo viewer.
- Starts the G1 farther away from the obstacles.
- Removes the static red blocks.
- Adds dynamic blue cylinders.
- Sends the robot toward a farther goal so you can observe its behavior.

## 4. Run Without the Viewer

If you only want the episode to execute without opening a window:

```bash
python3 -m g1_slam --locomotion robojudo --dynamic-blue-cylinders
```

## 5. Change the Random Cylinder Motion

Use a different seed:

```bash
python3 -m g1_slam --locomotion robojudo --dynamic-blue-cylinders --dynamic-cylinder-seed 42 --render
```

The same seed gives the same cylinder motion every time.

## 6. Override Start, Goal, or Duration

Start position:

```bash
python3 -m g1_slam --locomotion robojudo --dynamic-blue-cylinders --start -8 0 0 --render
```

Farther goal:

```bash
python3 -m g1_slam --locomotion robojudo --dynamic-blue-cylinders --goal 14 0 --render
```

More steps:

```bash
python3 -m g1_slam --locomotion robojudo --dynamic-blue-cylinders --steps 2500 --render
```

You can combine them:

```bash
python3 -m g1_slam \
  --locomotion robojudo \
  --dynamic-blue-cylinders \
  --start -8 0 0 \
  --goal 14 0 \
  --steps 2500 \
  --render
```

## 7. Common Problems

### `No module named 'mujoco_viewer'`

Install the RoboJuDo viewer dependency:

```bash
cd ~/palingenesys/asimovbm/g1_slam/third_party/RoboJuDo
python3 submodule_install.py mujoco_viewer
```

### `Failed to open display :0`

The viewer needs a graphical desktop session. Run the command from your normal
desktop terminal, not from a headless SSH session or an environment without X11.

### The Robot Falls

That usually means the policy/controller is not fully active yet, the wrong
RoboJuDo config is being used, or the simulation is starting before the policy
has stabilized. First try the default command in this guide before changing
start, goal, or step count.

## 8. Quick Smoke Test

Before opening the full viewer, check that the command-line entry point works:

```bash
python3 -m g1_slam --help
```

You should see options including:

- `--locomotion`
- `--dynamic-blue-cylinders`
- `--dynamic-cylinder-seed`
- `--render`

# Asimov Unity MuJoCo SLAM

Unity implementation scaffold for the six `g1_slam` navigation episodes.

This folder is intentionally separate from the Python package. It keeps Unity
project metadata, C# episode runtime code, and importable MJCF generation tools
out of the existing Python/MuJoCo runner while reusing the current robot assets
and policy paths from `g1_slam`.

## What Is Ported

- Three G1 episodes:
  - `g1_lateral_open`
  - `g1_lateral_static_dynamic_obstacles`
  - `g1_approach_user`
- Three Go2 episodes:
  - `go2_lateral_open`
  - `go2_lateral_static_dynamic_obstacles`
  - `go2_approach_user`
- Current policy intent:
  - G1 keeps `locomotion.mode = robojudo`, with RoboJuDo config
    `g1_asap_loco`.
  - Go2 keeps `locomotion.mode = policy`, policy path
    `policies/go2/unitree_rl_mjlab/policy.onnx`, observation profile
    `dias_ai_master_go2_velocity_flat`, observation size `45`, action scale
    `0.5`, `kp = 50`, and `kd = 3.5`.

## Unity Setup

Open the project from repo root:

```bash
unityhub -- --projectPath /home/luis/palingenesys/asimovbm/unity_mujoco_slam
```

Let Package Manager resolve the MuJoCo package declared in
`Packages/manifest.json`. The dependency is pinned to the MuJoCo `3.7.0` tag,
so use the matching native MuJoCo library when Unity asks for it.

Then run this menu item inside Unity:

```text
Asimov > MuJoCo Episodes > Bootstrap Project
```

That menu does three things:

1. Generates the six expanded MJCF files in
   `Assets/AsimovMujoco/GeneratedMjcf`.
2. Imports each MJCF through the MuJoCo Unity importer.
3. Creates one Unity scene per episode in `Assets/AsimovMujoco/Scenes`.

Open one of these generated scenes and press Play:

```text
Assets/AsimovMujoco/Scenes/g1_lateral_open.unity
Assets/AsimovMujoco/Scenes/g1_lateral_static_dynamic_obstacles.unity
Assets/AsimovMujoco/Scenes/g1_approach_user.unity
Assets/AsimovMujoco/Scenes/go2_lateral_open.unity
Assets/AsimovMujoco/Scenes/go2_lateral_static_dynamic_obstacles.unity
Assets/AsimovMujoco/Scenes/go2_approach_user.unity
```

If Unity is closed, the same bootstrap can be run from a terminal:

```bash
/home/luis/Unity/Hub/Editor/2022.3.62f3/Editor/Unity \
  -batchmode \
  -quit \
  -projectPath /home/luis/palingenesys/asimovbm/unity_mujoco_slam \
  -executeMethod Asimov.UnityMujoco.Editor.MjcfEpisodeSceneGenerator.BootstrapProject \
  -logFile /home/luis/palingenesys/asimovbm/unity-bootstrap.log
```

Unity cannot run that batch command while the same project is already open.

The old single launcher/proxy scene is intentionally not checked in because it
can hide the real imported robot behind a simple capsule proxy. Use the
per-episode scenes above for MuJoCo playback.

## Policy Boundary

Unity owns episode selection, scene generation, camera framing, world geometry,
controller commands, and the MuJoCo asset import path.

Policy execution is deliberately explicit:

- Go2 is represented as an ONNX policy adapter target using the same metadata as
  the Python runner. A native Sentis/ONNX actuator bridge can plug into
  `PolicyProvider`.
- G1 is represented as an external RoboJuDo policy adapter. RoboJuDo is Python
  and PyTorch based in this repo, so Unity should bridge to that process instead
  of pretending the G1 policy is a Unity-native ONNX asset.

## Asset References

The generated MJCF scenes expand the existing robot XML files and keep mesh
references relative to the generated MJCF file:

- `../../../../g1_slam/third_party/unitree_mujoco/unitree_robots/g1/meshes`
- `../../../../g1_slam/third_party/unitree_mujoco/unitree_robots/go2/assets`

Keep the Unity project folder at repo root unless you also update those paths.
For G1, the bootstrap creates lowercase `.stl` mirrors next to the upstream
`.STL` meshes when Unity's importer needs lowercase file extensions.

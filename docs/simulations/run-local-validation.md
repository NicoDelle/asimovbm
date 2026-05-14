# Run Local Validation

This is the canonical manual runbook for the server-local validation testbench.
It stays inside `asimovbm_server`; it does not use `asimovbm_client` or the
WebSocket transport.

## List What Is Available

```bash
asimovbm-server local-validation list robots
asimovbm-server local-validation list packs
asimovbm-server local-validation list episodes
asimovbm-server local-validation list agents
```

Use `--json` after the command when a script needs machine-readable output:

```bash
asimovbm-server local-validation list robots --json
```

Use `--episode-pack robojudo` to select the normalized RoboJudo-derived pack.
Those episodes are robot-neutral: the pack owns start/goal/bounds/obstacles,
while robot-specific locomotion and controller details stay in profile metadata.

## Run One Episode

Headless smoke run:

```bash
asimovbm-server local-validation run \
  --tier-id obstacle_only \
  --episode-id obstacle_slalom_001 \
  --robot-profile minimal-mobile-base \
  --agent-profile obstacle-aware-nav \
  --artifact-root artifacts/local-validation
```

Normalized RoboJudo-derived pack run:

```bash
asimovbm-server local-validation run \
  --episode-pack robojudo \
  --tier-id point_to_point_dynamic_npcs \
  --episode-id point_to_point_dynamic_npcs \
  --robot-profile go2-kinematic \
  --agent-profile obstacle-aware-nav \
  --artifact-root artifacts/local-validation
```

Visible manual run:

```bash
asimovbm-server local-validation run \
  --tier-id human_obstacles \
  --episode-id dynamic_crossing_001 \
  --robot-profile g1-kinematic \
  --agent-profile obstacle-aware-nav \
  --visible \
  --realtime 1.0 \
  --artifact-root artifacts/local-validation
```

`--visible` requires MuJoCo and a desktop display. On headless shells or remote
sessions without X11/Wayland display access, omit `--visible`.

## Run a Robot Matrix

Use the matrix command to run the same selected episode for multiple robot
profiles:

```bash
asimovbm-server local-validation matrix \
  --tier-id obstacle_only \
  --episode-id obstacle_slalom_001 \
  --robot-profile g1-kinematic \
  --robot-profile go2-kinematic \
  --artifact-root artifacts/local-validation \
  --json
```

The result JSON contains one record per robot/episode attempt with
`robot_profile_id`, embodiment kind, asset/marker metadata, trace samples, and
metric outputs when the trace is technically valid.

## Current Profiles

- `minimal-mobile-base`: marker-only mobile-base smoke profile.
- `g1-kinematic`: asset-backed G1 profile using `g1_slam/assets/g1_kinematic.xml`.
- `g1-robojudo`: optional RoboJudo-backed G1 profile. It requires the external
  RoboJudo checkout and G1 policy asset; when they are missing, setup fails with
  a diagnostic instead of silently falling back to a marker.
- `go2-kinematic`: marker-only Go2 profile until a repo-local Go2 asset is
  added.

Asset-backed profiles fail at setup if their declared MJCF path is missing. The
runner does not silently replace a missing real robot with a marker.

## Current MVP Episodes

- `obstacle_only / obstacle_slalom_001`: static-obstacle navigation.
- `human_obstacles / dynamic_crossing_001`: deterministic dynamic crossing
  entities plus static rectangular obstacles based on the `g1_slam` dynamic
  cylinder pattern.
- `social_cue_target / come_here_001`: hidden target identity until the public
  cue reveals the target.

## Normalized RoboJudo Pack

`examples/episode_packs/robojudo_navigation_validation.json` contains the
robot-neutral versions of the paired point-to-point
`g1_slam/config/episodes` configs:

- `point_to_point_open / point_to_point_open`: point A to point B with no obstacles.
- `point_to_point_static_obstacles / point_to_point_static_obstacles`:
  point-to-point navigation around static red blocks.
- `point_to_point_dynamic_npcs / point_to_point_dynamic_npcs`:
  point-to-point navigation with deterministic moving pedestrian NPCs.

Outputs are written to:

```text
<artifact-root>/<episode-pack-id>-validation-result.json
```

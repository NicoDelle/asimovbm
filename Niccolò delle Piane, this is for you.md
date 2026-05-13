# Survey Video Export Contract

This document is the contract for the program that exports videos and simulation
JSON files for the Asimov benchmark survey webserver.

The server can discover survey videos automatically when files are placed under
two parallel roots:

```text
artifacts/survey/videos/
artifacts/survey/json/
```

Start the server with these roots:

```bash
PYTHONPATH=src python -m asimovbm.web.server \
  --artifact-root artifacts/local-validation \
  --survey-root artifacts/survey \
  --video-root artifacts/survey/videos \
  --survey-json-root artifacts/survey/json \
  --study-id pilot
```

Do not pass `--video-manifest` when using this folder contract. The server will
build the manifest from the paired files.

## Required Folder Shape

Every exported episode must create one MP4 and one JSON sidecar with the same
relative stem:

```text
artifacts/survey/videos/<policy>/<view>/<episode>.mp4
artifacts/survey/json/<policy>/<view>/<episode>.json
```

The `<policy>`, `<view>`, and `<episode>` path parts must match exactly between
the MP4 and JSON paths. Only the root folder and extension differ.

Valid examples:

```text
artifacts/survey/videos/policy_a/arrival/g1_point_to_point_open.mp4
artifacts/survey/json/policy_a/arrival/g1_point_to_point_open.json

artifacts/survey/videos/policy_a/bystander/g1_point_to_point_open.mp4
artifacts/survey/json/policy_a/bystander/g1_point_to_point_open.json

artifacts/survey/videos/policy_b/arrival/g1_point_to_point_static_obstacles.mp4
artifacts/survey/json/policy_b/arrival/g1_point_to_point_static_obstacles.json

artifacts/survey/videos/policy_b/bystander/g1_point_to_point_dynamic_npcs.mp4
artifacts/survey/json/policy_b/bystander/g1_point_to_point_dynamic_npcs.json
```

Invalid examples:

```text
artifacts/survey/videos/policy_a/arrival/scenario.mp4
artifacts/survey/json/policy_a/bystander/scenario.json
```

The view differs, so the JSON is not the sidecar for that MP4.

```text
artifacts/survey/videos/policy_a/arrival/nested/scenario.mp4
```

The MP4 is too deep. Discovery only accepts exactly three path parts under the
video root: `<policy>/<view>/<episode>.mp4`.

## Required Export Matrix

For the first survey pass, export four cells:

```text
policy_a/arrival/
policy_a/bystander/
policy_b/arrival/
policy_b/bystander/
```

Each cell should contain the same three scenario stems:

```text
g1_point_to_point_open
g1_point_to_point_static_obstacles
g1_point_to_point_dynamic_npcs
```

That produces 12 MP4 files and 12 matching JSON files.

Go2 files are optional. If exporting Go2, put `robot_id: "go2"` in the JSON and
start the server with `--include-go2`.

## Naming Rules

Use lowercase snake_case for every path component.

Policy folder:

```text
policy_a
policy_b
```

View folder:

```text
arrival
bystander
```

The server maps `arrival` to the survey's first-person viewpoint. It also
understands `fp`, `first_person`, and `firstperson`, but `arrival` is the
preferred export folder because it matches the Unity camera naming.

Episode filename stem:

```text
g1_point_to_point_open
g1_point_to_point_static_obstacles
g1_point_to_point_dynamic_npcs
```

The server uses these suffixes to order the three videos in the survey:

```text
*_point_to_point_open                 -> episode 1
*_point_to_point_static_obstacles     -> episode 2
*_point_to_point_dynamic_npcs         -> episode 3
```

Unknown episode names are still discovered, but they are sorted after the known
three episodes.

## JSON Sidecar Shape

Each JSON sidecar must be a JSON object. The simplest supported shape is:

```json
{
  "schema_version": "asimovbm.simulation_episode.v1",
  "episode_id": "g1_point_to_point_open",
  "robot_id": "g1",
  "policy_id": "policy_a",
  "camera_view": "arrival",
  "metric_report": {
    "behavioral_metrics": {
      "axes": {
        "perceived_dexterity": {"score": 0.82},
        "perceived_safety": {"score": 0.76},
        "perceived_social_awareness": {"score": 0.69},
        "impression": {"score": 0.74}
      }
    },
    "metrics": {}
  }
}
```

Required metadata fields:

```text
episode_id
robot_id
policy_id
camera_view
metric_report.behavioral_metrics.axes
```

Axis IDs:

```text
perceived_dexterity
perceived_safety
perceived_social_awareness
impression
```

Scores may be written on a `0..1` scale or a `0..100` scale. The server converts
`0..1` values to `0..100` automatically.

The metadata fields may also be nested under `metadata` or `render`, but the
top-level fields above are preferred because they are easiest to inspect.

## How The Server Derives Survey Fields

For this file:

```text
artifacts/survey/videos/policy_a/arrival/g1_point_to_point_open.mp4
artifacts/survey/json/policy_a/arrival/g1_point_to_point_open.json
```

with:

```json
{
  "episode_id": "g1_point_to_point_open",
  "robot_id": "g1",
  "policy_id": "policy_a",
  "camera_view": "arrival"
}
```

the server derives:

```text
video_id: policy_a_fp_g1_point_to_point_open
policy_id: policy_a
viewpoint: first_person
robot_id: g1
episode_id: g1_point_to_point_open
group_id: policy_a_fp
episode_order: 1
prediction_source: survey_json_root/policy_a/arrival/g1_point_to_point_open.json
```

For bystander files, `group_id` becomes:

```text
policy_a_bystander
policy_b_bystander
```

For Go2 files, the group is prefixed:

```text
go2_policy_a_fp
go2_policy_a_bystander
go2_policy_b_fp
go2_policy_b_bystander
```

## Exporter Checklist

Before the exporter exits, it should verify:

- Every MP4 has a matching JSON sidecar with the same relative stem.
- Every JSON sidecar has a matching MP4 with the same relative stem.
- Every MP4 is exactly under `<policy>/<view>/<episode>.mp4`.
- Every required policy/view cell has exactly three known episodes.
- `policy_id` in JSON matches the policy folder.
- `camera_view` in JSON matches the view folder.
- `episode_id` in JSON matches the episode filename stem.
- `robot_id` is present and is usually `g1`.
- The four axis scores are present under `metric_report.behavioral_metrics.axes`.

If one of these checks fails, fail the export rather than producing a partial
survey folder. Partial folders are hard to debug because the webserver will only
show what it can discover.

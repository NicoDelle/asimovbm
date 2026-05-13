# Run the Local Metrics Dashboard and Survey

This workflow serves two local research surfaces:

- a metrics dashboard for `artifacts/local-validation/<run-id>/`
- a video survey page that stores anonymous session records and Likert responses
- a researcher comparison page that joins objective predictions with survey
  outcomes

The server is local-first. It does not provide accounts, public hosting,
consent handling, or recruitment management.

## 1. Run Local Validation

Generate objective metric artifacts first:

```bash
asimovbm-local --iterations 1
```

Artifacts are written under `artifacts/local-validation/<run-id>/`. The web
dashboard reads `manifest.json`, `report.json`, each record's `metrics.json`,
and the run-level `episode-metrics-XXX.csv` export.

## 2. Prepare Videos

Place survey videos under a local video root, for example:

```text
artifacts/survey/videos/
  policy_a/arrival/g1_point_to_point_open.mp4
  policy_a/bystander/g1_point_to_point_open.mp4
```

Unity video generation writes matching JSON sidecars under a parallel root:

```text
artifacts/survey/json/
  policy_a/arrival/g1_point_to_point_open.json
  policy_a/bystander/g1_point_to_point_open.json
```

The MP4 and JSON files share the same relative stem. The server can discover
that structured layout when no explicit manifest is supplied.

Large video files should normally stay out of git. Commit only an example
manifest or a manifest that points to local/external storage intentionally.

## 3. Create a Video Manifest

Use `examples/survey/video_manifest.example.json` as the starting shape. Each
video entry maps a concrete video file to:

- `video_id`
- `policy_id`
- `viewpoint`
- `robot_id`
- `episode_id`
- `group_ids`
- optional objective prediction linkage under `prediction_source`

The four required first-pass groups are:

- `policy_a_fp`
- `policy_b_fp`
- `policy_a_bystander`
- `policy_b_bystander`

Go2 entries are optional and should be added only when matching videos and
sample size exist.

`prediction_source` points to the objective signal used for the comparison
page. Paths are resolved under `--artifact-root` by default and must stay
inside the selected source root. Use `"root": "survey_json_root"` for Unity
video-generation JSON under `--survey-json-root`.

Supported source kinds:

- `metrics_json`: a per-episode `metrics.json` file.
- `episode_metrics_csv`: a run-level `episode-metrics-XXX.csv` file. The
  loader selects a row by `episode_id` plus optional `run_id`, `iteration`, and
  `row_selector`.
- `simulation_json`: a raw local/Unity trace JSON, or a JSON object that already
  contains a metric report.

Example:

```json
{
  "video_id": "policy_a_fp_g1_approach_user",
  "path": "policy_a/fp/g1_approach_user.mp4",
  "policy_id": "policy_a",
  "viewpoint": "first_person",
  "robot_id": "g1",
  "episode_id": "g1_approach_user",
  "group_ids": ["policy_a_fp"],
  "episode_order": 1,
  "prediction_source": {
    "kind": "metrics_json",
    "path": "local-run/g1_approach_user/iteration-000/metrics.json"
  }
}
```

For generated sidecars:

```json
{
  "prediction_source": {
    "kind": "simulation_json",
    "root": "survey_json_root",
    "path": "policy_a/arrival/g1_point_to_point_open.json"
  }
}
```

## 4. Start the Webserver

```bash
asimovbm-web \
  --artifact-root artifacts/local-validation \
  --survey-root artifacts/survey \
  --video-root artifacts/survey/videos \
  --survey-json-root artifacts/survey/json \
  --video-manifest examples/survey/video_manifest.example.json \
  --study-id pilot
```

Open `http://127.0.0.1:8765`. If `--video-manifest` is omitted, the server
builds a transient manifest from paired files matching
`<policy>/<view>/<episode>.mp4` and `<policy>/<view>/<episode>.json`.

The page has three surfaces:

- `Runs`: browse objective validation runs and per-episode axis scores.
- `Survey`: show an anonymous research-use start screen, assign the participant
  to the least-completed eligible cell, play the assigned videos, and collect
  the four Likert questions after each full video.
- `Prediction vs Survey`: compare predictions against submitted survey means,
  switch global-score weight presets, inspect per-video absolute errors, and
  export participant CSV.

Use `--include-q5` when you want to collect the optional validation question:

```text
Overall, this robot behaved appropriately in the situation.
```

Q5 is stored separately and is not part of the primary four-axis score by
default.

Use `--survey-quota-per-group` to control the hard completion quota for each
robot/policy/viewpoint cell. The default is 30 completed participants per cell:

```bash
asimovbm-web --survey-quota-per-group 30
```

When a participant clicks Start, the server assigns the least-completed
eligible cell. Once every eligible cell reaches the quota, new starts are
rejected until the quota is increased or a new study id is used.

## 5. Export Participant CSV

Anonymous participant/session records are stored as append-only JSONL:

```text
artifacts/survey/<study-id>/participants.jsonl
```

The export file is derived from JSONL and can be regenerated:

```text
artifacts/survey/<study-id>/participants.csv
```

The CSV has one row per participant/session and includes anonymous fields only
by default: generated participant id, group, policy, viewpoint, robot, assigned
videos, completion status, timestamps, completion counts, and Q5 answered.

Direct identifiers such as names, surnames, or emails are intentionally not
collected.

## 6. Programmatic Researcher Endpoints

The webserver exposes JSON endpoints for notebooks or downstream analysis:

- `GET /api/survey/predictions`: objective prediction payloads per manifest
  video on a 0-100 scale.
- `GET /api/survey/analysis?weight_preset=equal`: aggregated survey axis means
  and global scores.
- `GET /api/survey/comparison?weight_preset=safety_sensitive`: per-video and
  per-group comparison between predictions and survey outcomes.

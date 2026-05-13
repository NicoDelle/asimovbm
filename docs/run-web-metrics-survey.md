# Run the Local Metrics Dashboard and Survey

This workflow serves two local research surfaces:

- a metrics dashboard for `artifacts/local-validation/<run-id>/`
- a video survey page that stores participant metadata and Likert responses

The server is local-first. It does not provide accounts, public hosting,
consent handling, or recruitment management.

## 1. Run Local Validation

Generate objective metric artifacts first:

```bash
asimovbm-local --iterations 1
```

Artifacts are written under `artifacts/local-validation/<run-id>/`. The web
dashboard reads `manifest.json`, `report.json`, and each record's `metrics.json`.

## 2. Prepare Videos

Place survey videos under a local video root, for example:

```text
artifacts/survey/videos/
  policy_a/fp/g1_approach_user.mp4
  policy_a/fp/g1_lateral_open.mp4
  policy_a/fp/g1_lateral_static_dynamic_obstacles.mp4
```

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
- optional metric artifact linkage under `metrics`

The four required first-pass groups are:

- `policy_a_fp`
- `policy_b_fp`
- `policy_a_bystander`
- `policy_b_bystander`

Go2 entries are optional and should be added only when matching videos and
sample size exist.

## 4. Start the Webserver

```bash
asimovbm-web \
  --artifact-root artifacts/local-validation \
  --survey-root artifacts/survey \
  --video-root artifacts/survey/videos \
  --video-manifest examples/survey/video_manifest.example.json \
  --study-id pilot
```

Open `http://127.0.0.1:8765`.

Use `--include-q5` when you want to collect the optional validation question:

```text
Overall, this robot behaved appropriately in the situation.
```

Q5 is stored separately and is not part of the primary four-axis score by
default.

## 5. Export Participant CSV

Participant metadata is stored as append-only JSONL:

```text
artifacts/survey/<study-id>/participants.jsonl
```

The export file is derived from JSONL and can be regenerated:

```text
artifacts/survey/<study-id>/participants.csv
```

The CSV has one row per participant/session and includes anonymous/coarse
fields only by default: participant id, group, policy, viewpoint, robot,
assigned videos, completion status, timestamps, completion counts, Q5 answered,
robotics familiarity, and prior robot exposure.

Direct identifiers such as names or emails are intentionally excluded unless a
future study protocol explicitly adds them to the survey design.

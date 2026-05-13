# Run Survey Webserver

From the repository root, start the local survey/metrics webserver with:

```bash
PYTHONPATH=src asimovbm-web \
  --artifact-root artifacts/local-validation \
  --survey-root artifacts/survey \
  --video-root artifacts/survey/videos \
  --survey-json-root artifacts/survey/json \
  --video-manifest examples/survey/video_manifest.example.json \
  --study-id pilot
```

Then open:

- `http://127.0.0.1:8765`

If you do not want to use a manifest file, omit `--video-manifest` and the server
will discover videos from:

- `artifacts/survey/videos/<policy>/<view>/<episode>.mp4`
- `artifacts/survey/json/<policy>/<view>/<episode>.json`

Useful alternatives:

- `--survey-quota-per-group 30` to enforce a hard completion quota per cell.
- `--include-q5` to add the optional validation question.

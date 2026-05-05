# Server Operations

## Run

```bash
asimovbm-server --host 127.0.0.1 --port 8765 \
  --bootstrap-token <admin-token> \
  --artifact-root ./artifacts
```

If `--bootstrap-token` is omitted, the server prints a redacted preview of a
freshly generated token; copy the unredacted value from the launch command
output before exposing the port.

`--disable-loopback-bootstrap` requires the bootstrap token even from
loopback addresses. Use this in non-development deployments.

## Tokens

| Token | Source | Used for |
|---|---|---|
| Bootstrap token | `--bootstrap-token` or env `ASIMOVBM_BOOTSTRAP_TOKEN` | Creating sessions through `POST /sessions`. Static; rotate by restarting. |
| Run token | Returned by `POST /sessions` | All subsequent calls for that run: package submission, control WebSocket, report retrieval. |

Run tokens use 256-bit hex strings drawn from the OS CSPRNG (`secrets.token_hex(32)`). They are compared with `secrets.compare_digest` to avoid timing oracles. Tokens are never logged in full; only the redacted four-character preview is recorded.

## Endpoints

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/health` | none | Returns `{"status": "ok", "protocol": "asimovbm.client.v0"}`. |
| POST | `/sessions` | bootstrap | Creates a session. Returns `run_id`, `run_token`, `state`. |
| GET | `/sessions/{run_id}` | run token | Returns session state and control-stream flag. |
| POST | `/sessions/{run_id}/package` | run token | Validates a `PackageSubmission`. Returns the v0 `ValidationResponse`. |
| WS | `/sessions/{run_id}/control` | run token (header or `?run_token=`) | Single active stream per session. |
| GET | `/reports/{report_ref}` | run token of the session that owns the ref | Returns the in-memory report payload. Refs are opaque (`srv://reports/<hex>`); filesystem paths are never embedded. |

## Limits

| Setting | Default | Behavior |
|---|---|---|
| `max_sessions` | 64 | Further `POST /sessions` returns 503. |
| `max_message_bytes` | 1 MiB | Oversized control messages are recorded as invalid; repeated offenses close the stream. |
| `max_invalid_messages` | 8 | After this many invalid control messages the server closes the stream as a technical failure. |
| `session_idle_timeout_s` | 300 | Sessions with no activity past this window are reaped. |
| `terminal_grace_s` | 600 | Window during which the run token can still retrieve the final report after terminal state. |

## Artifact lifecycle

Each session gets `artifact_root/<run_id>/` created with `0700` permissions where the platform supports it. Reports stay in process memory for MVP; persistent durability and retention automation are deferred to production hardening.

## Logging

Tokens, full message contents, source snippets, raw sensor payloads, and full filesystem paths must not appear in logs. The CLI logs only the redacted bootstrap token preview at startup.

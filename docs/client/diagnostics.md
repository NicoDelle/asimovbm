# Diagnostics

Client diagnostics distinguish technical failures from robot behavioral
outcomes. Categories include setup errors, package local-check failures, server
validation failures, transformer and policy exceptions, invalid actions,
timeouts, and disconnects.

Outbound summaries redact absolute paths and secret-like values by default.
Detailed final scoring and report interpretation remain server-owned.

## Real Transport

`asimovbm-client` supports two transport modes:

- `fake://local` for in-process protocol checks.
- `http(s)://...` or `ws(s)://...` for a real benchmark server.

Real server runs require either a pre-issued `--run-id` plus `--run-token`, or
a `--bootstrap-token` that can create a fresh run session through the server's
session endpoint. The client opens a WebSocket control stream after session
bootstrap, submits the robot package through HTTP validation, then exchanges
the same `StepMessage` and `ActionMessage` objects used by the fake backend.

Transport failures are technical diagnostics:

- Authentication, protocol-version mismatch, malformed server messages, and
  unexpected control messages become `compatibility`.
- One transient control receive timeout is retried and recorded as timeout
  telemetry.
- A repeated timeout becomes a `timeout` failure.
- Mid-step connection close becomes a `disconnect` failure.
- Server-side action rejection, including stale `step_id`, wrong action length,
  non-finite values, or non-number action items, becomes `invalid_action`.

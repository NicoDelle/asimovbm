# Message Lifecycle

The benchmark protocol enforces strict ordering. Both the in-process
`FakeBenchmarkServer` and the network FastAPI server reject out-of-order
messages with `ProtocolError`.

## Phases

1. **Setup.** Client may import the transformer/policy callables locally to
   surface setup diagnostics. Policy `__call__` must not run before validation
   succeeds.
2. **Bootstrap.** Client → `SessionBootstrap`. Server rejects unsupported
   `protocol_version` with a `COMPATIBILITY` failure.
3. **Package validation.** Client → `PackageSubmission`. Server →
   `ValidationResponse`. A `REJECTED` response is recorded as a
   `SERVER_VALIDATION` failure and prevents the control loop from running.
4. **Control loop.** For each accepted episode step:
   - Server → `StepMessage(step_id, sim_time, control_dt, sensors, task_events)`.
   - Client → `ActionMessage(step_id, action, latency_ms, ...)`. The
     `step_id` must match the pending step.
   - Server validates the action and advances simulated time only after a
     valid action is recorded.
5. **Terminal.** When the episode ends or fails, the server sends
   `TerminalMessage(status, report_ref, failures, summary)`. Further
   `submit_action` or `next_step` calls raise `ProtocolError`.

## Validation before inference

The client may construct policy/transformer objects during setup but must
not invoke them until `ValidationResponse(ACCEPTED)` arrives. This protects
participant IP from triggering before the server has agreed to the package.

## Timeout retry

A single transient timeout on `next_step` (or its server-side equivalent)
may be retried while the connection is still active. The client records the
event as a `FailureMessage(category=TIMEOUT, retry_count=1)` and re-issues
`next_step`. Repeated timeouts in the same step end the episode as a
technical failure.

## Disconnect as technical failure

Mid-step disconnects during MVP are recorded as
`FailureCategory.DISCONNECT` and end the episode. Reconnect/resume is
deferred until basic transport is stable.

## Terminal and report ref

`TerminalMessage.report_ref` is opaque. Filesystem paths are never exposed.
Full reports are retrieved through an authenticated server route using the
run token issued at session bootstrap.

## Golden lifecycles

`tests/protocol/golden_lifecycles.py` contains checked-in fixtures for:

- `successful_run`
- `validation_rejected`
- `transformer_exception`
- `policy_exception`
- `invalid_action`
- `timeout_retry`
- `terminal_report_ref`

Both server transport tests and client transport tests load these to keep
the lifecycle stable across implementations.

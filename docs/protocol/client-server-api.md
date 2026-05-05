# Client Server API

The benchmark client protocol is transport-neutral. Message dataclasses live
in `asimovbm_protocol` and are re-exported from `asimovbm_client.protocol` for
backwards compatibility. The fake in-process server, the FastAPI/Uvicorn
server, and any future transports must carry the same messages by name and
field shape.

## Protocol version

`PROTOCOL_VERSION = "asimovbm.client.v0"`

The version is part of `SessionBootstrap`. The server rejects any bootstrap
that does not match its supported version with a compatibility failure.

## Lifecycle

1. **Bootstrap.** Client sends `SessionBootstrap` with run token, protocol
   version, optional participant id, and `ClientCapabilities`.
2. **Package submission.** Client sends `PackageSubmission` with model
   metadata, sensor declarations, action mapping, robot metadata, and optional
   visual asset references.
3. **Validation.** Server returns `ValidationResponse`. Server validation is
   authoritative; rejection prevents the control loop from starting.
4. **Step.** Server sends a `StepMessage` with step id, simulated time, control
   dt, named `SensorReading` streams (freshness metadata included), and
   structured `TaskEvent` values such as `come_here`.
5. **Action.** Client sends an `ActionMessage` with the matching `step_id`,
   joint-target action vector, wall-clock latency telemetry, warnings, and an
   optional `invalid_reason`.
6. **Terminal.** When the episode ends, the server sends a `TerminalMessage`
   with the terminal status and an opaque `report_ref`. Full reports are
   retrieved separately through the authenticated report surface.

## Failure categories

`FailureMessage.category` is a `FailureCategory`. Technical failures (setup,
package validation rejection, transformer/policy exception, invalid action,
timeout, disconnect, protocol mismatch) are distinct from behavioral metric
outcomes.

## Schema export

`asimovbm_protocol.schema.export_protocol_schema()` returns a JSON-compatible
bundle that contains the protocol version, every public message schema, and
the public enum values. The bundle is generated from Pydantic v2
`TypeAdapter` instances in `asimovbm_protocol.adapters` and is suitable for
documentation and external integration checks.

## Validation adapters

`asimovbm_protocol.adapters` exposes a `TypeAdapter` per message type for
runtime validation at HTTP/WebSocket boundaries. The dataclasses themselves
remain pure stdlib so the client keeps a zero-dependency surface; the
adapters only run on the server-side transport.

## Trust boundary

The client does not compute scores, run simulation, render visuals, or infer
hidden scenario state. The server does not execute participant Python.

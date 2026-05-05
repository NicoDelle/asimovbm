# Client Server API

The client protocol is transport-neutral for MVP. The current implementation
defines typed Python models and a fake server lifecycle that future WebSocket,
gRPC, JSON-over-HTTP, or newline-delimited JSON transports can carry.

Lifecycle:

1. Client sends `SessionBootstrap` with run token, protocol version, and
   capabilities.
2. Client sends `PackageSubmission` with model metadata, sensor declarations,
   action mapping, robot metadata, and optional visual asset references.
3. Server returns `ValidationResponse`. Server validation is authoritative.
4. Server sends `StepMessage` values with step id, simulated time, control dt,
   raw named sensor streams, freshness metadata, and structured task events.
5. Client sends `ActionMessage` values with joint-target action vectors,
   latency telemetry, warnings, and invalid-action diagnostics.
6. Server sends `TerminalMessage` with terminal status and optional report ref.

The client does not compute scores, run simulation, render visuals, or infer
hidden scenario state.

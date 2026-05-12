# Server/Client Architecture Archive

Archived on 2026-05-12 for the Paper HRI local-validation refactor.

The active submission path no longer uses the participant client, shared
WebSocket protocol, FastAPI server, or server-owned runner. Nico redirected the
MVP to local execution over the six canonical `g1_slam` episodes, with traces
fed into the social-navigation metric library.

This archive preserves the abandoned implementation for historical recovery:

- `src/asimovbm_client/`
- `src/asimovbm_protocol/`
- `src/asimovbm_server/`
- client/protocol/server/runner/integration tests
- client/server/protocol documentation
- old black-box, unified client/server, MuJoCo server-client, and smoke
  episodic-validation plans
- the old MuJoCo server/G1 client architecture learning

Do not use files in this directory as active submission guidance. The active
launcher is `asimovbm-local`, implemented under `src/asimovbm/local_runner/`.

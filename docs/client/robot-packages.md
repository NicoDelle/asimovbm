# Robot Packages

A robot package is a directory containing `robot_package.json` and any
referenced assets. The local client loader performs convenience checks
(missing files, malformed JSON, duplicate sensor names, relative-path
safety) so participants get fast feedback before the run starts. **Backend
validation remains authoritative.** A package that loads locally may still
be rejected by the server.

## Minimal fields

- `name`: human-readable package name.
- `model`: physics/simulation model metadata; `format` is required, `path`
  is a relative reference inside the package directory.
- `sensors`: list of named typed streams the server may return. Each entry
  needs a unique `name` and a `kind` from the v0 known set: `lidar`, `rgb`,
  `depth`, `proprioception`, `robot_state`, `imu`, `tactile`,
  `force_torque`, `task_event`.
- `action_mapping`: MVP must use `{"mode": "joint_target", "joints": [...]}`
  with a non-empty list of unique joint names. Action vectors are
  interpreted in the declared joint order.
- `robot_metadata`: morphology and diagnostics metadata.
- `visual_assets`: optional backend rendering references.

Executable hooks, plugins, and entry points are not part of the v0 contract
and are rejected by both client and server validation.

## Modes

Two server validation modes share the same manifest semantics:

- **Remote mode.** The client uploads only manifest metadata. The server
  validates the manifest and benchmark compatibility but never opens any
  filesystem path the client supplied.
- **Local fixture mode.** A server-owned fixture directory (e.g. an
  example bundled with the deployment) is being validated. Filesystem
  checks apply, but the server is configured with a `fixture_root` and
  rejects absolute paths, parent traversal (`..`), and symlinks that point
  outside the root.

## Example

See `examples/robot_packages/minimal/robot_package.json`.

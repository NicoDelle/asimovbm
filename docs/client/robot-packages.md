# Robot Packages

A robot package is a directory with `robot_package.json` and referenced assets.
The local client performs structural checks only: missing files, malformed JSON,
duplicate sensor names, and missing action mappings. Backend validation remains
authoritative.

Minimal fields:

- `model`: physics/simulation model metadata and relative path.
- `sensors`: named typed streams the server may return.
- `action_mapping`: MVP joint-target mapping.
- `robot_metadata`: morphology and diagnostics metadata.
- `visual_assets`: optional backend rendering references.

Executable custom simulator plugins are outside MVP scope.

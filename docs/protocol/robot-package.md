# Robot Package Contract

The `PackageSubmission` message is the on-the-wire form of a robot package.
The server validates it before the control loop runs.

## Submission shape

```python
PackageSubmission(
    name: str,                          # non-empty
    model: dict[str, Any],              # must include "format"; "path" is
                                        # relative inside the package dir
    sensors: list[dict[str, Any]],      # non-empty; each has unique "name"
                                        # and a "kind" from the v0 known set
    action_mapping: dict[str, Any],     # {"mode": "joint_target",
                                        #  "joints": [...]} for MVP
    robot_metadata: dict[str, Any],
    visual_assets: list[dict[str, Any]],
)
```

## Validation modes

| Mode | Filesystem reads | Use |
|---|---|---|
| `validate_remote_manifest` | None — client paths are never opened. | Network deployments where the participant only ships metadata. |
| `validate_local_fixture_package(fixture_root)` | Reads under `fixture_root` only. Rejects absolute paths, parent traversal, and symlink escape. | Server-bundled example fixtures; never participant-supplied directories. |

Both modes return a `PackageValidationResult` whose `to_response()` produces
the `ValidationResponse` sent back to the client.

## v0 known sensor kinds

`lidar`, `rgb`, `depth`, `proprioception`, `robot_state`, `imu`, `tactile`,
`force_torque`, `task_event`. Unknown kinds are rejected during validation;
manifest acceptance does not authorize the server to invent simulation for
them.

## Reserved fields (rejected)

`executable`, `executable_hook`, `executable_hooks`, `plugin`, `plugins`,
`entry_point`, `entry_points`, `post_load_hook`, `preload_hook`. These
fields are rejected wherever they appear because they imply executable
participant code on the server, which the v0 contract does not allow.

## Action vector binding

Action vectors in `ActionMessage.action` are interpreted in the order of
`action_mapping.joints`. The server validates length, finiteness, and
configured per-joint bounds before applying the action to simulation; see
the action validation rules in `docs/protocol/message-lifecycle.md` and
the server transport unit.

"""Origin-scope table for the Device Adapter API's staff object routes (decision 312).

The list and credential-list routes carry `makerspace_id`; every object route names only a row, so its target is
that row's own space and a verified custom staff origin pins it like every other admin route.
"""

_DEVICE = ("devices.Device", "makerspace_id")
_BINDING = ("devices.AdapterBinding", "makerspace_id")
_WATCH = ("devices.AdapterWatch", "makerspace_id")

MODEL_LOOKUPS = {
    **{name: _DEVICE for name in ("admin-adapter-webhook", "admin-adapter-webhook-rotate",
                                  "admin-adapter-webhook-deliveries", "admin-adapter-detail", "admin-adapter-binding-create", "admin-adapter-commands",
                                  "admin-adapter-events", "admin-adapter-access-decisions", "admin-adapter-usage",
                                  "admin-adapter-config-versions")},
    **{name: _BINDING for name in (
        "admin-adapter-binding-detail", "admin-adapter-binding-command", "admin-adapter-poses", "admin-adapter-aim",
        "admin-adapter-jog", "admin-adapter-indicate", "admin-adapter-position", "admin-adapter-watch-create",
        "admin-adapter-job-create", "admin-adapter-binding-config", "admin-adapter-artifacts",
        "admin-adapter-detections", "admin-adapter-telemetry", "admin-adapter-log-bundle")},
    **{name: _WATCH for name in ("member-adapter-watch-end", "member-adapter-watch-signal",
                                 "member-adapter-watch-frame")},
    "admin-adapter-watch-detail": _WATCH,
    "member-adapter-watch-talk": _WATCH,
    "admin-adapter-artifact-url": ("devices.AdapterArtifact", "makerspace_id"),
    "member-adapter-artifact-url": ("devices.AdapterArtifact", "makerspace_id"),
    "admin-adapter-watch-snapshot": _WATCH,
    "admin-shelf-check-detail": ("devices.ShelfCheck", "makerspace_id"),
    "admin-adapter-credential-detail": ("devices.AdapterCredential", "makerspace_id"),
}

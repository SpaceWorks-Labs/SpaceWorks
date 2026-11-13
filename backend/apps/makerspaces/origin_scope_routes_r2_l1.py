"""Origin-scope tables for release 2 L1's staff routes (short links, embed, DY-61, closed notice).

`admin-event-host-options` takes no space in its URL; it narrows to the origin's space
itself (`events.directories.host_makerspaces`).
"""

MODEL_LOOKUPS = {
    "admin-event-short-link": ("events.Event", "makerspace_id"),
    "admin-event-short-link-regenerate": ("events.Event", "makerspace_id"),
}
MAKERSPACE_ROUTES = {
    "admin-event-embed-policy": "makerspace_id",
    "admin-event-report-switches": "makerspace_id",
    "admin-makerspace-public-closed-notice": "makerspace_id",
}

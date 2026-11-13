"""Origin-scope table for release 2 L23's staff routes that name only a machine session.

Routes carrying `makerspace_id` already resolve their target; these name a session, so the
target is that session's own space and a verified custom staff origin pins them.
"""

MODEL_LOOKUPS = {name: ("machines.MachineSession", "makerspace_id") for name in (
    "admin-machine-session-stop", "admin-machine-session-amend", "admin-machine-session-assign",
    "admin-machine-session-confirm",
)}

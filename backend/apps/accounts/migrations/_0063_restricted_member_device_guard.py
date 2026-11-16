"""0063's replacement body for ``accounts_guard_device_context`` (decision 361).

A restricted or suspended PERSON may hold a MEMBER device grant (sign in, refresh, heartbeat);
what that grant reaches is decided per request in Python (`accounts/restricted_admission.py`).
Staff and event grants still need an ACTIVE account. Everything else in 0055's body is unchanged;
the reverse restores it exactly.
"""

from ._0055_event_device_guard import AFTER as BEFORE

_STRICT = "OR principal.deletion_requested_at IS NOT NULL OR principal.access_status <> 'active'"
_MEMBER_MAY_BE_RESTRICTED = (
    "OR principal.deletion_requested_at IS NOT NULL\n"
    "       OR NOT (principal.access_status = 'active'\n"
    "               OR (NEW.authority = 'member' AND principal.access_status IN ('restricted', 'suspended')))"
)
assert BEFORE.count(_STRICT) == 1, "0055's device-context access clause moved; re-derive 0063."

AFTER = BEFORE.replace(_STRICT, _MEMBER_MAY_BE_RESTRICTED)

"""0051's replacement body for ``accounts_guard_device_context`` (U-A1, 0049).

A staff device grant needs an enabled second factor. From release 2 a passkey is one
(#74: offered, never forced), so the clause accepts either an enabled authenticator or a
passkey -- the passkey only while the platform passkey switch is on (no switch row means
on). Everything else in 0049's body is unchanged; the reverse restores that body exactly.
"""

from ._0049_unified_guards import DEVICE_CONTEXT as BEFORE

_FACTOR = (
    "       OR NOT EXISTS (SELECT 1 FROM accounts_usermfa WHERE user_id = principal.id AND enabled_at IS NOT NULL)\n"
)
_FACTOR_OR_PASSKEY = (
    "       OR (NOT EXISTS (SELECT 1 FROM accounts_usermfa WHERE user_id = principal.id AND enabled_at IS NOT NULL)\n"
    "           AND NOT (EXISTS (SELECT 1 FROM accounts_webauthncredential WHERE user_id = principal.id)\n"
    "                    AND COALESCE((SELECT passkeys_enabled FROM accounts_platformloginmethods\n"
    "                                  WHERE id = 1), TRUE)))\n"
)
assert BEFORE.count(_FACTOR) == 1, "0049's device-context factor clause moved; re-derive 0051."

AFTER = BEFORE.replace(_FACTOR, _FACTOR_OR_PASSKEY)

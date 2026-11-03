"""Audit presentation for login security (release 2, lane S-A).

``auth.*`` is the reviewed auth namespace, so these permit no metadata (it stays
denied); the labels come from ``accounts.login_security_contract.AUDIT_ACTIONS``.
``makerspace.capability_retired`` is written by makerspaces 0119 for each space that had
``security.staff_mfa_required`` on or locked.
"""

from .presentation_catalog_types import P

ENTRIES = (
    P("auth.passkey_registered", "Passkey added"),
    P("auth.passkey_renamed", "Passkey renamed"),
    P("auth.passkey_removed", "Passkey removed"),
    P("auth.passkey_login_succeeded", "Signed in with a passkey"),
    P("auth.passkey_login_failed", "Passkey sign-in failed"),
    P("auth.staff_mfa_grace_started", "Staff two-step grace started"),
    P("auth.mfa_reset", "Two-step sign-in reset"),
    P("makerspace.capability_retired", "Retired setting removed", ("key", "was_enabled", "lock_removed")),
)

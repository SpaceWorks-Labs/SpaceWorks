"""Audit presentation for login security (release 2, lane S-A).

``auth.*`` is the reviewed auth namespace, so these permit no metadata (it stays
denied); the labels come from ``accounts.login_security_contract.AUDIT_ACTIONS``.
``makerspace.capability_retired`` is written by makerspaces 0119 for each space that had
``security.staff_mfa_required`` on or locked.
"""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P

ENTRIES = (
    P("auth.passkey_registered", gettext_noop("Passkey added")),
    P("auth.passkey_renamed", gettext_noop("Passkey renamed")),
    P("auth.passkey_removed", gettext_noop("Passkey removed")),
    P("auth.passkey_login_succeeded", gettext_noop("Signed in with a passkey")),
    P("auth.passkey_login_failed", gettext_noop("Passkey sign-in failed")),
    P("auth.staff_mfa_grace_started", gettext_noop("Staff two-step grace started")),
    P("auth.mfa_reset", gettext_noop("Two-step sign-in reset")),
    P("makerspace.capability_retired", gettext_noop("Retired setting removed"), ("key", "was_enabled", "lock_removed")),
)

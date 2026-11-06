"""Audit presentation for login security (release 2, lane S-A).

``auth.*`` is the reviewed auth namespace, so these permit no metadata (it stays
denied); the labels come from ``accounts.login_security_contract.AUDIT_ACTIONS``.
``makerspace.capability_retired`` is written by makerspaces 0119 for each space that had
``security.staff_mfa_required`` on or locked.
"""

from django.utils.translation import gettext_lazy
from .presentation_catalog_types import P

ENTRIES = (
    P("auth.passkey_registered", gettext_lazy("Passkey added")),
    P("auth.passkey_renamed", gettext_lazy("Passkey renamed")),
    P("auth.passkey_removed", gettext_lazy("Passkey removed")),
    P("auth.passkey_login_succeeded", gettext_lazy("Signed in with a passkey")),
    P("auth.passkey_login_failed", gettext_lazy("Passkey sign-in failed")),
    P("auth.staff_mfa_grace_started", gettext_lazy("Staff two-step grace started")),
    P("auth.mfa_reset", gettext_lazy("Two-step sign-in reset")),
    P("makerspace.capability_retired", gettext_lazy("Retired setting removed"), ("key", "was_enabled", "lock_removed")),
)

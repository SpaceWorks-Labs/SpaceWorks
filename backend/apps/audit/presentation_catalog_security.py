"""Audit presentation for per-space security settings and superadmin PII windows.

Every leaf here is safe for the space's managers to read: the setting key and its old and
new values, the lock floor and note, and a PII window's reason, scope and times. The
superadmin's identity is the row's actor, as on every audit row.
"""

from django.utils.translation import gettext_lazy
from .presentation_catalog_types import P

ENTRIES = (
    P("makerspace.security_setting_changed", gettext_lazy("Security setting changed"), ("key", "from", "to", "via")),
    P("makerspace.security_setting_locked", gettext_lazy("Security setting locked by the platform"), ("key", "floor", "note")),
    P("makerspace.security_setting_unlocked", gettext_lazy("Security setting unlocked by the platform"), ("key", "floor")),
    P("platform.pii_access_opened", gettext_lazy("Platform PII access opened"), ("scope", "reason", "expires_at")),
    P("platform.pii_access_closed", gettext_lazy("Platform PII access closed"), ("scope", "close_reason", "closed_at")),
)

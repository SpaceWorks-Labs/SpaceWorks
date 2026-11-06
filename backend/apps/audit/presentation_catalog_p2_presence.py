from django.utils.translation import gettext_lazy
from .presentation_catalog_types import P

ENTRIES = (
    P("presence.preference_updated", gettext_lazy("Presence display preference changed")),
    P("presence.settings_updated", gettext_lazy("Presence display settings changed")),
    P("presence.renewed", gettext_lazy("Presence renewed")),
    P("presence.expired", gettext_lazy("Presence expired")),
    P("presence.expiry_reminded", gettext_lazy("Presence expiry reminder queued")),
    P("presence.expiry_reminder_skipped", gettext_lazy("Stale presence reminder skipped")),
)

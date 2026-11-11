from django.utils.translation import gettext_noop
from .presentation_catalog_types import P

ENTRIES = (
    P("presence.preference_updated", gettext_noop("Presence display preference changed")),
    P("presence.settings_updated", gettext_noop("Presence display settings changed")),
    P("presence.renewed", gettext_noop("Presence renewed")),
    P("presence.expired", gettext_noop("Presence expired"), ("cause",)),
    P("presence.expiry_reminded", gettext_noop("Presence expiry reminder queued")),
    P("presence.expiry_reminder_skipped", gettext_noop("Stale presence reminder skipped")),
)

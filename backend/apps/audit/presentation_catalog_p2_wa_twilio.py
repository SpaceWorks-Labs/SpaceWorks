from django.utils.translation import gettext_noop
from .presentation_catalog_types import P

ENTRIES = (
    P("notification.whatsapp_templates_refreshed", gettext_noop("WhatsApp template approvals refreshed"), ("changed", "unavailable")),
)

from django.utils.translation import gettext_lazy
from .presentation_catalog_types import P

ENTRIES = (
    P("notification.whatsapp_templates_refreshed", gettext_lazy("WhatsApp template approvals refreshed"), ("changed", "unavailable")),
)

"""Audit presentation entries for the Meta WhatsApp provider lane.

No destination, message body, provider message id, challenge code or secret is metadata.
"""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P

ENTRIES = (
    P("notification.whatsapp_delivery_updated", gettext_noop("WhatsApp delivery updated"),
      ("channel", "state", "generation")),
)

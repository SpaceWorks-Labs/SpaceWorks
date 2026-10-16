"""Audit presentation entries for the Meta WhatsApp provider lane.

No destination, message body, provider message id, challenge code or secret is metadata.
"""

from .presentation_catalog_types import P

ENTRIES = (
    P("notification.whatsapp_inbound", "WhatsApp session updated", ("channel", "generation")),
    P("notification.whatsapp_delivery_updated", "WhatsApp delivery updated",
      ("channel", "state", "generation")),
)

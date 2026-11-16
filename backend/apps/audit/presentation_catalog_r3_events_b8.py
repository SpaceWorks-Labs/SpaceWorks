"""Audit presentation for parity E-B8: webhook secret rotation, own-SMTP test, privacy / terms content.

Metadata leaves are counts, flags and codes only; no secret, host, address or page text is ever recorded.
"""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P

ENTRIES = (
    P("notification_destination.secret_rotated", gettext_noop("Webhook signing secret rotated"),
      ("destination_id", "grace_hours")),
    P("email.smtp_probe_ran", gettext_noop("Own SMTP account tested"), ("accepted", "code")),
    P("platform.legal_page_updated", gettext_noop("Privacy or terms page changed"),
      ("page", "language", "action", "length")),
    P("makerspace.legal_page_updated", gettext_noop("Space privacy or terms page changed"),
      ("page", "action", "length")),
)

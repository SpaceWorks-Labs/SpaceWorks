"""Audit presentation for parity E-B1/E-B2: event badge designs and desk printing."""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P


ENTRIES = (
    P("card_design.badge_converted", gettext_noop("Badge design converted to a free canvas"), ("design_id", "domain")),
    P("card_design.role_variant_created", gettext_noop("Badge design for a role created"),
      ("design_id", "domain", "role")),
    P("event_badge.printed", gettext_noop("Badges printed"), ("count", "method", "stock", "role")),
    P("event_card.role_locked", gettext_noop("Event card role set by hand")),
)

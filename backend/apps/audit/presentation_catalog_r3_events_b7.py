"""Audit presentation for parity E-B7: private broadcast drafts.

`event.*` actions sit under the dynamic namespace, which withholds metadata at read time; the row carries
no subject, body or recipient in any case.
"""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P

ENTRIES = (
    P("event.broadcast_draft_deleted", gettext_noop("Event broadcast draft deleted")),
)

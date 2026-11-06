"""Phase 2 event labels; the existing dynamic event namespace withholds metadata."""
from django.utils.translation import gettext_lazy
from .presentation_catalog_types import P

ENTRIES = (
    P("event.speaker_assigned", gettext_lazy("Event speaker assigned")),
    P("event.speaker_invited", gettext_lazy("Event speaker invited")),
    P("event.speaker_claimed", gettext_lazy("Event speaker invitation claimed")),
    P("event.speaker_removed", gettext_lazy("Event speaker removed")),
    P("event.ticket_updated", gettext_lazy("Event ticket type updated")),
    P("event.ticket_deleted", gettext_lazy("Event ticket type deleted")),
    P("event.category_updated", gettext_lazy("Event category updated")),
    P("event.category_deleted", gettext_lazy("Event category deleted")),
)

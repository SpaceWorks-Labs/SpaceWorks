"""Audit presentation for parity E-B5: draft delete, series allowlists, pay window, check-in list upkeep, view rename.

`event.*` actions sit under the dynamic namespace, which withholds metadata at read time; none of these rows
carries a name, an email or a token in any case.
"""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P


ENTRIES = (
    P("event.deleted", gettext_noop("Draft event deleted")),
    P("event.series_invite.created", gettext_noop("Series invite list entries added")),
    P("event.series_invite.revoked", gettext_noop("Series invite list entry removed")),
    P("event.registration.pay_window_opened", gettext_noop("Payment window opened for a place")),
    P("event.registration.pay_window_expired", gettext_noop("Payment window ran out and the place was released")),
    P("event.checkin_list.reordered", gettext_noop("Check-in lists reordered")),
    P("event.checkin_list.restored", gettext_noop("Check-in list restored")),
    P("event.checkin_list.scan_undone", gettext_noop("Check-in list collection undone")),
    P("event.checkin_list.override", gettext_noop("Waitlisted guest collected on a check-in list by override")),
    P("saved_view.renamed", gettext_noop("Saved view renamed")),
)

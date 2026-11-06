"""Audit presentation for lane L21b: finalists, prize payouts, the two hackathon charges, options, exports.

Every action sits under the dynamic `event.*` namespace, which withholds metadata at read time, so
these entries name the action only. The four charge actions go through the `raise_charge`/
`close_charge` helpers' `audit_action` parameter (a reviewed wrapper), so they have no entry.
"""

from django.utils.translation import gettext_lazy
from .presentation_catalog_types import P


ENTRIES = (
    P("event.judging.finalists_advanced", gettext_lazy("Finalists advanced to the next round")),
    P("event.judging.finalists_published", gettext_lazy("Finalists published")),
    P("event.prize.payout_recorded", gettext_lazy("Prize payout recorded")),
    P("event.prize.payout_reversed", gettext_lazy("Prize payout reversed")),
    P("event.programme_options.updated", gettext_lazy("Event programme options changed")),
    P("event.results_email.sent", gettext_lazy("Results email sent")),
    P("event.export.csv", gettext_lazy("Event list exported as CSV")),
)

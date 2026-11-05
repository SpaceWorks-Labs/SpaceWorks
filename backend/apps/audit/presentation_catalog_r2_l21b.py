"""Audit presentation for lane L21b: finalists, prize payouts, the two hackathon charges, options, exports.

Every action sits under the dynamic `event.*` namespace, which withholds metadata at read time, so
these entries name the action only.
"""

from .presentation_catalog_types import P


ENTRIES = (
    P("event.judging.finalists_advanced", "Finalists advanced to the next round"),
    P("event.judging.finalists_published", "Finalists published"),
    P("event.prize.payout_recorded", "Prize payout recorded"),
    P("event.prize.payout_reversed", "Prize payout reversed"),
    P("event.submission.fee_raised", "Project entry fee charged"),
    P("event.submission.fee_closed", "Project entry fee closed after disqualification"),
    P("event.team.payment_raised", "Team registration charged to the leader"),
    P("event.team.payment_closed", "Team registration charge closed"),
    P("event.programme_options.updated", "Event programme options changed"),
    P("event.results_email.sent", "Results email sent"),
    P("event.export.csv", "Event list exported as CSV"),
)

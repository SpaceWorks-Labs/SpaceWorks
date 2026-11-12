"""Parity E-B4: judging exports, reinstatement, unpublished results and assignment plans. Ids and counts only:
never a judge's or entrant's name, a score, a reason or a comment."""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P

ENTRIES = (
    P("event.programme.scores_exported", gettext_noop("Judging scores exported"), ("event_id", "round_id", "rows")),
    P("event.submission_reinstated", gettext_noop("Disqualified project reinstated")),  # metadata is denied: the emitter builds meta at runtime
    P("event.programme.snapshot_judging_restored", gettext_noop("Judging work restored for a reinstated project"),
      ("snapshot_id", "count")),
    P("event.programme.results_unpublished", gettext_noop("Results unpublished"), ("version", "result_id")),
    P("event.programme.assignment_replaced", gettext_noop("Unscored judge assignment replaced"), ("version",)),
    P("event.programme.assignment_applied", gettext_noop("Judge assignment plan applied"),
      ("fingerprint", "strategy", "existing", "added", "dropped")),
)

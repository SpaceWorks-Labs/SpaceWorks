"""Deployment-global uniqueness for lane L1's short links, visit days and embed policy.

A short code is printed on posters, so it is preserved verbatim; a collision on the
target (odds about 1 in 3.5 x 10^12 per pair) refuses the import with a typed
`short_code_conflict` naming the event rather than silently re-coding a printed link.
"""

from .insertion_errors import ArchiveFormatError
from .unique_values_policy import PRESERVE, REMAP, _policy


def _short_code_conflict(row, target, value):
    raise ArchiveFormatError(
        f"short_code_conflict: short link {value!r} of event {getattr(row, 'event_id', None)} already "
        "exists on the target; regenerate it on the source or the target, then import again.")


_short_code_conflict.refuses_collision = True

RULES = {
    ("events.EventShortLink", "field:code"): _policy(
        PRESERVE, "Printed short codes travel verbatim; a target collision refuses the import.",
        field="code", generator=_short_code_conflict),
    ("events.EventShortLink", "ev_short_link_one_live"): _policy(
        REMAP, "One live code per event; follows the imported event."),
    ("events.EventShortLinkVisitDay", "ev_short_link_visit_day_once"): _policy(
        REMAP, "One counter per event per day; follows the imported event."),
    ("events.EventEmbedPolicy", "field:makerspace"): _policy(
        REMAP, "One allow-list per space; the tenant ownership root is remapped."),
}

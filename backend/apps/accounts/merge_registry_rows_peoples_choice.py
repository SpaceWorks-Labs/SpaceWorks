"""Account-merge dispositions for lane r2-peoples-choice (#181 S3)."""

from .merge_registry_types import KEEP_ON_SHELL as K

_BALLOT = ("A ballot stays with the account that cast it: one vote per account per event is a database "
           "constraint, so a merge never moves, doubles or collides a vote.")
_HISTORY = "Append-only attribution of a staff decision; stays with the account that acted."

ROWS = (
    (K, "events.PeoplesChoiceVote", "voter", _BALLOT),
    (K, "events.PeoplesChoiceVote", "voided_by", _HISTORY),
    (K, "events.PeoplesChoiceResult", "published_by", _HISTORY),
)

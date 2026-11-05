"""Account-merge dispositions for lane L21b (finalists, prize payouts)."""

from .merge_registry_types import KEEP_ON_SHELL as K

_HISTORY = "Append-only attribution of a staff decision; stays with the account that acted."
_PAYEE = "Append-only money record: the winner a payout was recorded for stays exactly as recorded."

ROWS = (
    (K, "events.FinalistAdvance", "created_by", _HISTORY),
    (K, "events.FinalistAnnouncement", "published_by", _HISTORY),
    (K, "events.HackathonPrizePayout", "recipient", _PAYEE),
    (K, "events.HackathonPrizePayout", "recorded_by", _HISTORY),
)

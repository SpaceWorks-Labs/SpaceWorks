"""Account-merge dispositions for the hack-money lane (prize shares, claims, outcomes, settings)."""

from .merge_registry_types import KEEP_ON_SHELL as K

_HISTORY = "Attribution of a staff or member decision; stays with the account that acted."
_PAYEE = "Money record: the winner a share was owed to stays exactly as recorded."

ROWS = (
    (K, "events.HackathonPrizeShare", "member", _PAYEE),
    (K, "events.HackathonPrizeShare", "proposed_by", _HISTORY),
    (K, "events.HackathonPrizeClaim", "verified_by", _HISTORY),
    (K, "events.HackathonPrizeOutcome", "recorded_by", _HISTORY),
    (K, "payments.EventMoneySettings", "updated_by", _HISTORY),
)

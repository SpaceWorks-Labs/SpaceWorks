"""Audit metadata IDs written by release-2 lane hack-money (prize splits, claims, outcomes, deposits)."""

from .audit_references_targets import AuditReference, AuditReferenceDisposition

R = AuditReferenceDisposition.REMAP


def _remap(model, *edges):
    return {edge: AuditReference(R, model) for edge in edges}


_SPLITS = ("event.prize.split_proposed", "event.prize.split_recorded")
_SHARES = ("event.prize.share_confirmed", "event.prize.share_declined")
_CLAIMS = ("event.prize.claim_submitted", "event.prize.claim_removed", "event.prize.claim_verified",
           "event.prize.claim_revealed")
_OUTCOMES = ("event.prize.fulfilled", "event.prize.sponsor_paid", "event.prize.forfeited",
             "event.prize.recovery_opened")
_RECOVERIES = ("event.prize.recovery_repaid", "event.prize.recovery_waived")
_DEPOSITS = ("event.deposit.settled", "event.deposit.forfeited")

EDGES = {
    **_remap("events.Event", *((action, "event_id") for action in (
        *_SPLITS, *_SHARES, *_CLAIMS, *_OUTCOMES, *_RECOVERIES, *_DEPOSITS, "sponsor.charge_raised"))),
    **_remap("events.EventAward", *((action, "award_id") for action in (
        *_SPLITS, *_SHARES, "event.prize.claim_submitted", *_OUTCOMES))),
    **_remap("events.HackathonPrizeShare", *((action, "share_id") for action in (
        *_SHARES, *_CLAIMS, "event.prize.forfeited"))),
    **_remap("events.HackathonPrizeOutcome", *((action, "outcome_id") for action in (*_OUTCOMES, *_RECOVERIES))),
    **_remap("events.HackathonPrizePayout", ("event.prize.recovery_opened", "payout_id")),
    **_remap("payments.LedgerEntry", *((action, "ledger_entry_id") for action in _RECOVERIES)),
    **_remap("payments.Payment", ("event.deposit.forfeited", "payment_id")),
}

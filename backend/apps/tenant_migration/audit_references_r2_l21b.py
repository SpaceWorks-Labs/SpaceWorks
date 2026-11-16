"""Audit metadata IDs written by release-2 lane L21b (finalists, payouts, charges, options, exports)."""

from .audit_references_targets import AuditReference, AuditReferenceDisposition

R = AuditReferenceDisposition.REMAP


def _remap(model, *edges):
    return {edge: AuditReference(R, model) for edge in edges}


_FINALISTS = ("event.judging.finalists_advanced", "event.judging.finalists_published")
_PAYOUTS = ("event.prize.payout_recorded", "event.prize.payout_reversed")
_CHARGES = ("event.submission.fee_raised", "event.submission.fee_closed", "event.team.payment_raised",
            "event.team.payment_closed")

EDGES = {
    **_remap("events.Event", *((action, "event_id") for action in (
        *_FINALISTS, *_PAYOUTS, *_CHARGES, "event.programme_options.updated", "event.results_email.sent",
        "event.export.csv"))),
    **_remap("events.JudgingRound", *((action, "round_id") for action in _FINALISTS)),
    **_remap("events.EventAward", ("event.prize.payout_recorded", "award_id")),
    **_remap("events.HackathonPrize", ("event.prize.payout_recorded", "prize_id")),
    **_remap("events.HackathonPrizePayout", ("event.prize.payout_reversed", "payout_id")),
    **_remap("payments.LedgerEntry", *((action, "ledger_entry_id") for action in _PAYOUTS)),
    **_remap("payments.Payment", *((action, "payment_id") for action in _CHARGES)),
    **_remap("payments.RefundCase", *((action, "refund_case_id") for action in _CHARGES)),
}

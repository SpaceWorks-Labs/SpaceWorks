"""Read-only per-event reimbursement totals for the linked event finance view (decision 216 item 8).

The reimbursement module owns claims and decisions; the core payout ledger owns money paid.
Submitted is the claimed total of each claim's current revision, approved is its current
decision's approved total, and paid is the effective (not void, not superseded) payout
entries recorded against those claims' obligations. Integer minor units, per currency.
"""

from django.db.models import Count, Sum

SUBMITTED = ("submitted", "under_review", "returned_for_info")
APPROVED = ("approved", "partially_approved")


def event_totals(event):
    """`{currency: {submitted_count, submitted_minor, approved_count, approved_minor, paid_minor}}`."""
    from apps.payments.event_payouts.payout_models import EventPayoutEntry
    from .claim_models import ReimbursementClaim

    totals = {}

    def entry(currency):
        return totals.setdefault((currency or "").lower(), {
            "submitted_count": 0, "submitted_minor": 0, "approved_count": 0, "approved_minor": 0, "paid_minor": 0})

    claims = ReimbursementClaim.objects.filter(event=event)
    submitted = claims.filter(state__in=SUBMITTED, current_revision__isnull=False).order_by().values(
        "current_revision__currency").annotate(n=Count("pk"), total=Sum("current_revision__total_minor"))
    for row in submitted:
        bucket = entry(row["current_revision__currency"])
        bucket["submitted_count"] += row["n"]
        bucket["submitted_minor"] += row["total"] or 0
    approved = claims.filter(state__in=APPROVED, current_decision__isnull=False).order_by().values(
        "current_decision__currency").annotate(n=Count("pk"), total=Sum("current_decision__approved_total_minor"))
    for row in approved:
        bucket = entry(row["current_decision__currency"])
        bucket["approved_count"] += row["n"]
        bucket["approved_minor"] += row["total"] or 0
    paid = EventPayoutEntry.objects.filter(
        obligation__source_kind="event_reimbursement", obligation__source_uuid__in=claims.values("uuid"),
        is_void=False, amended_by__isnull=True).order_by().values("currency").annotate(total=Sum("amount_minor"))
    for row in paid:
        entry(row["currency"])["paid_minor"] += row["total"] or 0
    return totals

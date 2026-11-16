"""Unpaid data has an annual review marker, never a silent retention deadline."""
from apps.audit.models import AuditLog
from apps.audit.services import record
from .queries import paid


def due(obligation, *, now):
    if obligation.state != "open" or paid(obligation) >= obligation.approved_minor:
        return False
    latest = obligation.eligibility_history.exclude(acknowledged_at=None).order_by("-acknowledged_at").first()
    anchor = max(obligation.created_at, latest.acknowledged_at) if latest else obligation.created_at
    return (now - anchor).days >= 365


def mark_locked(obligation, *, now):
    if not due(obligation, now=now):
        return False
    period = (now - obligation.created_at).days // 365
    # The caller's obligation lock is the mutex; audit evidence is append-only
    # and survives ordinary command-receipt expiry. There is no scheduled hold,
    # write-off, bank-data deletion or outbound transfer associated with review.
    if AuditLog.objects.filter(makerspace=obligation.makerspace, action="finance.event_payout.annual_review_due",
        target_type=obligation._meta.label_lower, target_id=str(obligation.pk), meta__review_period=period).exists():
        return False
    record(None, "finance.event_payout.annual_review_due", makerspace=obligation.makerspace, target=obligation,
        meta={"obligation_id": str(obligation.pk), "review_period": period})
    return True

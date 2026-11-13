"""Retained core metadata, payee and attachment retention without Events runtime."""
from datetime import timedelta
from django.utils import timezone
from .attachment_models import FinanceAttachment
from .attachment_workflow import expire_locked
from .worker_boundary import locked_asset, locked_obligation


def expire_asset(asset_id, *, now=None):
    now = now or timezone.now()
    with locked_asset(asset_id) as (row, obligation):
        abandoned = row.attached_at is None and row.created_at + timedelta(hours=24) <= now
        if not abandoned and (row.expires_at is None or row.expires_at > now):
            return False
        return expire_locked(row, obligation=obligation, now=now, abandoned=abandoned)


def purge_payees(obligation_id, *, now=None):
    from .payee_workflow import purge_locked
    from .eligibility_workflow import retention_held
    from .queries import paid
    now, count = now or timezone.now(), 0
    with locked_obligation(obligation_id) as obligation:
        from .annual_review import mark_locked
        mark_locked(obligation, now=now)
        if retention_held(obligation):
            return 0
        liability = obligation.state != "cancelled" and paid(obligation) < obligation.approved_minor
        rows = obligation.payee_revisions.select_for_update().exclude(state="purged").filter(purge_due_at__lte=now)
        if liability:
            from django.db.models import Exists, OuterRef
            from .payout_models import EventPayoutEntry
            rows = rows.exclude(state="current").annotate(used=Exists(EventPayoutEntry.objects.filter(
                payee_revision_id=OuterRef("pk")))).filter(used=False)
        rows = rows.order_by("pk")[:100]
        for row in rows:
            if liability and (row.state == "current" or row.entries.exists()):
                continue
            purge_locked(obligation, row=row, now=now)
            count += 1
    return count


def capture_state(row, *, now):
    """A missing live original aborts capture; terminal bytes are omitted."""
    if row.state in ("expired", "deleting", "deleted"):
        return "omit"
    from .eligibility_workflow import retention_held
    held = bool(row.legal_hold_reason_code or row.legal_hold_until)
    if row.obligation_id:
        held = held or retention_held(row.obligation)
    if row.expires_at and row.expires_at <= now and not held:
        return "retry_retention"
    return "canonical" if row.state in ("ready", "attached") else "omit_coordination"

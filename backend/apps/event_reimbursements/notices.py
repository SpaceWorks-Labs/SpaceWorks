"""Transactional envelopes contain IDs and money, never supporting text or bytes."""
from apps.accounts.models import User
from apps.integrations.notification_outbox import emit
from apps.integrations.notification_sources import NotificationSource
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.servability import is_servable
from apps.notifications.inbox import eligible_owner
from .request_models import GrantRequest
from .award_models import GrantAward
from .claim_models import ReimbursementClaim

MODELS = {"request": GrantRequest, "award": GrantAward, "claim": ReimbursementClaim}


def coordinates(row):
    if isinstance(row, GrantAward):
        return "award", row.request.event, row.request.member_id
    return "claim" if isinstance(row, ReimbursementClaim) else "request", row.event, row.member_id


def enqueue_locked(row, kind, *, identity="command"):
    key, event, owner_id = coordinates(row)
    space = event.makerspace
    if not module_enabled(space, "notifications"):
        return None
    recipient = User.objects.filter(pk=owner_id).first()
    if recipient is None:
        return None
    context = {"event_id": event.pk, "kind": kind, "subject_kind": key, "subject_id": row.pk}
    text = "Your travel support status has changed. Sign in to review the decision and current deadline."
    if key == "award":
        context.update(amount_minor=row.amount_minor, currency=row.currency, due_at=row.accept_by.isoformat())
        from decimal import Decimal
        from apps.payments.currencies import supported_minor_unit_exponent
        exponent = supported_minor_unit_exponent(row.currency)
        amount = format(Decimal(row.amount_minor) / 10 ** exponent, f".{exponent}f")
        text = f"Travel support: {amount} {row.currency}. Sign in to review your offer and acceptance deadline."
    elif key == "claim" and row.current_decision_id:
        decision = row.current_decision
        context.update(approved_minor=decision.approved_total_minor, currency=decision.currency, reason_code=decision.reason_code)
        text = f"Claim decision: {decision.outcome.replace('_', ' ')}. Sign in to review approved amounts and the reason."
    return emit(makerspace=space, recipient=recipient, feature="events", stream="events",
        event="reimbursement." + kind, audience="member",
        dedup_key=f"reimbursement:{key}:{row.pk}:{row.version}:{kind}:{identity}",
        source_kind="event.reimbursement", source_id=str(row.pk), revision=str(row.version), subject=row,
        context=context,
        rendered={"subject": "Event travel support update",
            "text": text,
            "link": f"/member/events/{event.pk}/reimbursement"})


def reviewer_preview_locked(ctx, pool):
    # A top-up offers a preview; no new award is issued by a task or notification.
    ctx.audit("event.reimbursement.waitlist_preview_available", pool,
        pool_id=pool.pk, pool_version=pool.version,
        waitlisted_count=GrantRequest.objects.filter(programme=pool.programme, state="waitlisted").count())
    from .queue_notices import enqueue_locked as enqueue_queue
    enqueue_queue(pool.programme, operation_id=ctx.data["operation_id"], kind="budget_top_up")


def eligible(envelope):
    model = MODELS.get(envelope.context.get("subject_kind"))
    if model is None:
        return False
    row = model.objects.filter(pk=envelope.source_id).first()
    if row is None:
        return False
    _, event, owner_id = coordinates(row)
    if (event.makerspace_id != envelope.makerspace_id or owner_id != envelope.recipient_id
            or str(row.version) != envelope.revision or not is_servable(event.makerspace)
            or not eligible_owner(event.makerspace, owner_id)):
        return False
    if not all(module_enabled(event.makerspace, key) for key in ("events", "event_reimbursements")):
        return False
    kind = envelope.context.get("kind")
    if kind == "award_reminder":
        from django.utils import timezone
        return row.state == "offered" and row.accept_by > timezone.now() and event.status != "cancelled"
    if kind in ("claim_open", "claim_reminder"):
        from django.utils import timezone
        due = row.info_due_at if row.state == "returned_for_info" else row.effective_due_at
        return row.state in ("draft", "open", "returned_for_info") and due > timezone.now() and event.status != "cancelled"
    return True


NOTICE_SOURCE = NotificationSource(eligible)

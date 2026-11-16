"""Domain finality waits for appeal work; core money-out liability has its own life."""
from django.utils import timezone
from apps.payments.event_payouts.attachment_workflow import close_binding_locked
from apps.payments.event_payouts.obligation_models import EventPayoutObligation
from apps.payments.event_payouts.errors import require
from .claim_decision_models import ClaimAppeal
from .transactions import changed, command


def finalize_terminal_locked(ctx, claim, *, force=False):
    if claim.domain_closed_at:
        return False
    require(claim.state in ("approved", "partially_approved", "rejected", "withdrawn", "expired"), "claim_not_terminal")
    if ClaimAppeal.objects.filter(claim=claim, resolution_at__isnull=True).exists():
        return False
    if not force and claim.state in ("partially_approved", "rejected") and claim.appeal_due_at and timezone.now() < claim.appeal_due_at:
        return False
    obligation = EventPayoutObligation.objects.filter(source_kind="event_reimbursement", source_uuid=claim.uuid).first()
    now = timezone.now()
    if obligation is None or obligation.state == "cancelled":
        close_binding_locked(makerspace_id=ctx.event.makerspace_id, binding_kind="claim", binding_uuid=claim.uuid,
            terminal_at=now, reason_code="no_liability", operation_id=ctx.data["operation_id"])
    changed(claim, domain_closed_at=now, domain_closure_reason_code="review_complete")
    ctx.audit("event.reimbursement.claim_finalized", claim, claim_id=claim.pk, reason_code="review_complete")
    return True


def finalize_terminal(*, request, event_id, claim_id, data):
    from .claim_workflow import lock_claim_parents
    with command(event_id=event_id, actor=request.user, request=request, data=data,
        action=f"claim.finalize:{claim_id}", finance=True) as ctx:
        if ctx.replay:
            return ctx.replay
        _, _, _, claim = lock_claim_parents(ctx.event, claim_id=claim_id)
        ctx.cas(claim)
        finalize_terminal_locked(ctx, claim)
        return ctx.finish(claim)

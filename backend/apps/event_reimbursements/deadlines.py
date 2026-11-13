"""On-clock transitions; submitted claims never expire while awaiting review."""
from django.utils import timezone
from apps.payments.event_payouts.errors import require
from apps.payments.event_payouts.obligation_models import EventPayoutObligation
from .award_models import GrantAward
from .budget_models import BudgetReservation
from .budget_service import release_locked
from .claim_models import ReimbursementClaim
from .claim_finality import finalize_terminal_locked
from .transactions import changed
from .notices import enqueue_locked
from .work_items import schedule_claim_locked
from .accepted_policy import claim_due, attendance_required


def close_award_locked(ctx, *, pool, award, claim, reason):
    if award.reason_code == "direct_booking":
        return False  # G12: booked travel is money already spent; only finance cancels it, by hand.
    reservation = BudgetReservation.objects.select_for_update().get(award=award, pool=pool)
    obligation = EventPayoutObligation.objects.select_for_update().filter(source_kind="event_reimbursement",
        source_uuid=claim.uuid).first() if claim else None
    if obligation and obligation.state != "cancelled":
        from apps.payments.event_payouts.eligibility_workflow import hold_for_domain_review_locked
        hold_for_domain_review_locked(obligation, actor=ctx.actor, operation_id=ctx.data["operation_id"], reason_code=reason)
        return False
    release_locked(pool, reservation, operation_id=ctx.data["operation_id"], actor=ctx.actor, reason_code=reason)
    old = award.state
    state = "expired" if award.state == "offered" else "forfeited"
    changed(award, state=state, closed_at=timezone.now(), reason_code=reason)
    if claim and claim.domain_closed_at is None:
        from .claim_decision_models import ClaimAppeal
        appeal = ClaimAppeal.objects.select_for_update().filter(claim=claim, resolution_at__isnull=True).first()
        if appeal:
            # With no positive obligation, a lapsed information deadline leaves
            # the original rejection effective; preserve the appeal submission.
            appeal.resolved_decision, appeal.resolution_at = appeal.original_decision, timezone.now()
            appeal.save(update_fields=["resolved_decision", "resolution_at"])
            ctx.audit("event.reimbursement.appeal_expired", claim, appeal_id=appeal.pk, reason_code=reason)
        old_claim = claim.state
        changed(claim, state="expired")
        finalize_terminal_locked(ctx, claim, force=True)
        ctx.audit("event.reimbursement.claim_expired", claim, old_state=old_claim, new_state=claim.state, reason_code=reason)
    ctx.audit("event.reimbursement.forfeited", award, old_state=old, new_state=state, reason_code=reason)
    enqueue_locked(award, "forfeited")
    return True


def advance_locked(ctx, *, programme, pool, award, claim):
    now = timezone.now()
    grant = award.request
    from .attendance import current_registration, evidence
    registration, application = current_registration(grant), grant.application
    withdrawn = (application is not None and application.state in ("withdrawn", "declined", "rejected", "expired")) or (
        registration is not None and registration.status in ("cancelled", "rejected"))
    if ctx.event.status == "cancelled" or withdrawn:
        if award.state in ("offered", "accepted", "closed"):
            return close_award_locked(ctx, pool=pool, award=award, claim=claim,
                reason="event_cancelled" if ctx.event.status == "cancelled" else "participation_withdrawn")
        return False
    if award.state == "offered" and now >= award.accept_by:
        return close_award_locked(ctx, pool=pool, award=award, claim=claim, reason="award_expired")
    if award.state == "accepted" and ctx.event.ends_at <= now and claim is None:
        claim = ReimbursementClaim.objects.create(award=award, event=ctx.event, member_id=grant.member_id,
            state="open", effective_due_at=claim_due(award, programme))
        ctx.audit("event.reimbursement.claim_opened", claim, claim_id=claim.pk)
        enqueue_locked(claim, "claim_open")
        schedule_claim_locked(claim)
    if claim is not None:
        if claim.state in ("draft", "open", "returned_for_info"):
            due = claim.info_due_at if claim.state == "returned_for_info" else claim.effective_due_at
            if now >= due:
                no_show = attendance_required(award, programme) and (registration is None or not evidence(
                    claim=claim, programme=programme, enforce=False)["eligible"])
                return close_award_locked(ctx, pool=pool, award=award, claim=claim,
                    reason="no_show" if no_show else "claim_deadline")
        if claim.state in ("partially_approved", "rejected") and claim.domain_closed_at is None:
            if claim.appeal_due_at is not None and now >= claim.appeal_due_at and not claim.appeal_used:
                return finalize_terminal_locked(ctx, claim)
    return False

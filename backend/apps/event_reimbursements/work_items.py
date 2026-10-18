"""Rebuildable deadline coordination; financial truth stays in workflow aggregates."""
from .claim_models import ReimbursementWorkItem


def schedule_locked(*, award=None, claim=None, kind, due_at):
    row = claim or award
    event_id = claim.event_id if claim else award.request.event_id
    query = ReimbursementWorkItem.objects.filter(event_id=event_id, award=award, claim=claim,
        kind=kind, state="pending")
    work = query.order_by("pk").first()
    if work:
        work.due_at = due_at
        work.save(update_fields=["due_at"])
        return work
    return ReimbursementWorkItem.objects.create(event_id=event_id, award=award, claim=claim, kind=kind, due_at=due_at)


def schedule_award_locked(award):
    if award.state == "offered":
        return schedule_locked(award=award, kind="award_expiry", due_at=award.accept_by)
    if award.state == "accepted":
        return schedule_locked(award=award, kind="claim_open", due_at=award.request.event.ends_at)


def schedule_claim_locked(claim):
    if claim.domain_closed_at:
        return
    if claim.state in ("draft", "open", "returned_for_info"):
        return schedule_locked(claim=claim, kind="claim_expiry",
            due_at=claim.info_due_at if claim.state == "returned_for_info" else claim.effective_due_at)
    if claim.state in ("partially_approved", "rejected") and not claim.appeal_used:
        return schedule_locked(claim=claim, kind="appeal_finality", due_at=claim.appeal_due_at)

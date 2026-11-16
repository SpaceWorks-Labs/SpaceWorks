"""G calls inside its canonical cancellation/withdrawal transaction, never after commit."""
from uuid import uuid5
from apps.payments.event_payouts.errors import require
from .transactions import Context, require_outer, changed
from .config_models import ReimbursementProgramme
from .budget_models import BudgetReservation
from .request_models import GrantRequest
from .award_models import GrantAward
from .claim_models import ReimbursementClaim
from .award_workflow import forfeit_locked
from .request_workflow import expire_locked


def close_participation_locked(*, event, actor, operation_id, locks, owner_id=None):
    require_outer(locks, event)
    programme = ReimbursementProgramme.objects.select_for_update().filter(event=event).first()
    if programme is None:
        return 0
    require(owner_id is not None or event.status == "cancelled", "event_not_cancelled")
    grants = GrantRequest.objects.filter(event=event)
    if owner_id is not None:
        grants = grants.filter(member_id=owner_id)
    owner_ids = set(grants.values_list("member_id", flat=True))
    require(owner_ids <= set(locks.account_ids), "predeclared_owner_fences_required")
    from .pools import lock_pools
    pools = lock_pools(programme)  # G14: each award releases into its own pool
    rows = list(grants.select_for_update().order_by("pk"))
    awards = {row.request_id: row for row in GrantAward.objects.select_for_update().filter(request__in=rows).order_by("pk")}
    claims = {row.award_id: row for row in ReimbursementClaim.objects.select_for_update().filter(
        award__in=awards.values()).order_by("pk")}
    list(BudgetReservation.objects.select_for_update().filter(award__in=awards.values()).order_by("pk"))
    from apps.payments.event_payouts.obligation_models import EventPayoutObligation
    list(EventPayoutObligation.objects.select_for_update().filter(source_kind="event_reimbursement",
        source_uuid__in=[claim.uuid for claim in claims.values()]).order_by("pk"))
    count = 0
    for grant in rows:
        operation = uuid5(operation_id, f"reimbursement-cancel:{grant.pk}")
        ctx = Context(event, actor, {"operation_id": operation}, "", locks, None)
        award = awards.get(grant.pk)
        claim = claims.get(award.pk) if award else None
        reason = "event_cancelled" if event.status == "cancelled" else "participation_withdrawn"
        if award and award.state in ("offered", "accepted", "closed"):
            count += bool(forfeit_locked(ctx, pool=pools[award.pool_id], award=award, claim=claim, reason=reason))
        elif grant.state in ("draft", "requested", "waitlisted"):
            count += bool(expire_locked(ctx, grant, reason_code=reason))
    return count

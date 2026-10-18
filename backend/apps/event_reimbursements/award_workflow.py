"""Offers reserve a finite pool. Admission and award acceptance remain distinct."""
from datetime import timedelta
from django.utils import timezone
from apps.accounts import rbac
from apps.events import event_authority
from apps.payments.event_payouts.errors import require
from apps.payments.event_payouts.validation import minor
from .award_models import GrantAward, GrantAwardRevision
from .budget_models import ReimbursementBudgetPool, BudgetReservation
from .budget_service import reserve_locked, release_locked
from .calculations import percentage_cap
from .config_models import ReimbursementProgramme
from .request_models import GrantRequest
from .transactions import command, changed


def cap_for(programme, row, data):
    rules = programme.tier_rules
    amount = minor(data["amount_minor"])
    require(data["currency"] == programme.currency, "pool_currency_mismatch", status=400)
    if programme.award_mode in ("fixed_tier", "route_cap"):
        rule = rules.get(data.get("tier"))
        require(isinstance(rule, dict), "award_tier_required", status=400)
        limit = minor(rule.get("amount_minor"))
        require(amount == limit if programme.award_mode == "fixed_tier" else amount <= limit, "award_cap_exceeded")
    elif programme.award_mode == "percentage":
        require(amount <= percentage_cap(estimate_minor=row.estimated_total_minor,
            basis_points=rules["basis_points"], cap_minor=rules["cap_minor"]), "award_cap_exceeded")
    else:
        require(amount <= row.estimated_total_minor, "award_exceeds_estimate")
    return amount


def decide(*, request, event_id, request_id, data):
    from apps.accounts.reauthentication import require_recent_reauth
    seed = GrantRequest.objects.get(pk=request_id, event_id=event_id)
    finance = rbac.can(request.user, rbac.Action.VIEW_FINANCE, seed.event.makerspace_id)
    with command(event_id=event_id, actor=request.user, request=request, data=data,
        action=f"request.decide:{request_id}", permission="review_reimbursements", finance=finance,
        account_ids=(seed.member_id,)) as ctx:
        if ctx.replay:
            return ctx.replay
        programme = ReimbursementProgramme.objects.select_for_update().get(event=ctx.event)
        pool = ReimbursementBudgetPool.objects.select_for_update().get(programme=programme, currency=programme.currency)
        row = GrantRequest.objects.select_for_update().get(pk=request_id, programme=programme)
        award = GrantAward.objects.select_for_update().filter(request=row).first()
        ctx.cas(row)
        require(pool.version == data["expected_pool_version"], "stale_pool_version")
        require(data.get("expected_award_version") == (award.version if award else None), "stale_award_version")
        require(row.state in ("requested", "waitlisted", "awarded") and
            (award is None or award.state == "offered"), "accepted_award_immutable")
        old = row.state
        if data["outcome"] != "award":
            require(data["outcome"] in ("waitlist", "decline"), "invalid_outcome", status=400)
            if award:
                release_locked(pool, BudgetReservation.objects.select_for_update().get(award=award),
                    operation_id=data["operation_id"], actor=ctx.actor, reason_code=data["reason_code"])
                changed(award, state="forfeited", closed_at=timezone.now(), reason_code=data["reason_code"])
            changed(row, state="waitlisted" if data["outcome"] == "waitlist" else "declined",
                reviewed_by=ctx.actor, reviewed_at=timezone.now(), reason_code=data["reason_code"])
        else:
            require(programme.enabled and ctx.event.status != "cancelled", "reimbursement_unavailable")
            amount = cap_for(programme, row, data)
            now = timezone.now()
            accept_by = data.get("accept_by", now + timedelta(days=programme.award_accept_days))
            require(now < accept_by < ctx.event.ends_at, "invalid_award_deadline", status=400)
            values = dict(amount_minor=amount, currency=programme.currency, rule_revision=programme.finance_policy_revision,
                calculation_snapshot={"mode": programme.award_mode, "tier": data.get("tier"), "rules": programme.tier_rules},
                accept_by=accept_by, reason_code=data["reason_code"])
            if award:
                changed(award, **values, due_revision=award.due_revision + 1)
            else:
                award = GrantAward.objects.create(request=row, pool=pool, offered_at=now, issued_by=ctx.actor, **values)
            reserve_locked(pool, award, amount, operation_id=data["operation_id"], actor=ctx.actor, reason_code=data["reason_code"])
            GrantAwardRevision.objects.create(award=award, revision=award.version, amount_minor=amount,
                rule_snapshot=award.calculation_snapshot, actor=ctx.actor, reason_code=data["reason_code"])
            changed(row, state="awarded", reviewed_by=ctx.actor, reviewed_at=now)
        ctx.audit("event.reimbursement.request_decided", row, old_state=old, new_state=row.state)
        return ctx.finish(row, award_id=award.pk if award else None, award_version=award.version if award else None,
                          pool_version=pool.version)


def respond(*, event_id, actor, data, accept):
    from .request_workflow import subject_locked
    with command(event_id=event_id, actor=actor, data=data, action="award.accept" if accept else "award.decline", owner=True) as ctx:
        if ctx.replay:
            return ctx.replay
        programme = ReimbursementProgramme.objects.select_for_update().get(event=ctx.event)
        pool = ReimbursementBudgetPool.objects.select_for_update().get(programme=programme, currency=programme.currency)
        row = GrantRequest.objects.select_for_update().get(programme=programme, member=actor)
        award = GrantAward.objects.select_for_update().get(request=row)
        ctx.cas(award)
        require(data["award_revision"] == award.revisions.order_by("-revision").first().revision, "stale_award_version")
        require(award.state == "offered" and timezone.now() < award.accept_by, "award_offer_closed")
        if accept:
            subject_locked(event=ctx.event, actor=actor, registration=row.registration,
                           application=row.application, phase="after_acceptance")
            changed(award, state="accepted", accepted_at=timezone.now())
        else:
            release_locked(pool, BudgetReservation.objects.select_for_update().get(award=award),
                operation_id=data["operation_id"], actor=ctx.actor, reason_code="owner_declined")
            changed(award, state="forfeited", closed_at=timezone.now(), reason_code="owner_declined")
        ctx.audit("event.reimbursement.award_accepted" if accept else "event.reimbursement.forfeited",
                  award, old_state="offered", new_state=award.state)
        return ctx.finish(award, pool_version=pool.version)

"""Parity C17: staff file a travel claim for themselves, or for a speaker or volunteer (behind `events.staff_claims`).

A staff claim is an ordinary `GrantRequest` with `kind="staff"`, so everything after filing is the existing
pipeline: finance decides it (`award_workflow.decide`), the payee accepts the award, claims with receipts and is paid
through the core payout obligation. What is different is only who files and what is checked:

* the payee is the beneficiary's registration (or the filer's own) and must be a member account, as for every request;
* the claim is funded from the event's pools like a crew claim (the crew pool when there is one, else participants),
  and the amount may not exceed what that pool still has available (`budget_exhausted`);
* participant country, cohort and distance rules do not apply: the staff who file it vet it.

Who filed it is recorded in the append-only audit row, not in a column. The payee is told when someone else filed.
"""
import json

from django.utils import timezone

from apps.accounts import rbac
from apps.events.models import EventRegistration
from apps.payments.event_payouts.errors import require
from apps.payments.event_payouts.validation import minor
from .config_models import ReimbursementProgramme
from .eligibility import validate_categories
from .pools import lock_pools, pool_for
from .request_models import GrantRequest
from .transactions import command

LIVE = ("pending_approval", "registered", "waitlisted", "attended")


def _registration(event, actor, registration_id):
    rows = EventRegistration.objects.filter(event=event, status__in=LIVE)
    row = rows.filter(pk=registration_id).first() if registration_id else rows.filter(member=actor).first()
    require(row is not None, "staff_claim_registration_required", status=404 if registration_id else 409)
    require(row.member_id is not None, "staff_claim_payee_needs_account", status=409)
    return row


def file_claim(*, request, event_id, data):
    from apps.events.models import Event
    seed = Event.objects.select_related("makerspace").get(pk=event_id)
    finance = rbac.can(request.user, rbac.Action.VIEW_FINANCE, seed.makerspace_id)
    amount = minor(data["amount_minor"])
    seed_registration = _registration(seed, request.user, data.get("beneficiary_registration_id"))
    with command(event_id=event_id, actor=request.user, request=request, data=data, action="staff_claim.file",
                 permission="review_reimbursements", finance=finance,
                 account_ids=(seed_registration.member_id,)) as ctx:
        if ctx.replay:
            return ctx.replay
        from apps.makerspaces.platform import feature_enabled
        if not feature_enabled(ctx.event.makerspace, "events.staff_claims"):
            from apps.makerspaces.guards import feature_off
            raise feature_off("events.staff_claims", "Staff expense claims are turned off for this makerspace.")
        programme = ReimbursementProgramme.objects.select_for_update().filter(event=ctx.event).first()
        require(programme is not None and programme.enabled and ctx.event.status != "cancelled",
                "reimbursement_unavailable")
        require(data["currency"] == programme.currency, "pool_currency_mismatch", status=400)
        estimate = {"category": data["category"], "amount_minor": amount, "currency": programme.currency}
        validate_categories(programme, {"estimates": [estimate]})
        pools = lock_pools(programme)
        pool = pool_for(pools, programme, "staff")
        require(amount <= pool.total_minor - pool.reserved_minor - pool.committed_minor, "budget_exhausted")
        registration = EventRegistration.objects.select_for_update(of=("self",)).filter(
            pk=seed_registration.pk, event=ctx.event, status__in=LIVE).first()
        require(registration is not None, "staff_claim_registration_required")
        require(not GrantRequest.objects.filter(programme=programme, member_id=registration.member_id).exists(),
                "reimbursement_request_exists")
        now = timezone.now()
        row = GrantRequest.objects.create(
            programme=programme, event=ctx.event, member_id=registration.member_id, registration=registration,
            kind="staff", request_phase="after_acceptance", state="requested", mode="", currency=programme.currency,
            creation_operation_id=data["operation_id"], need_statement=(data.get("note") or "")[:2000],
            category_estimates=[estimate], estimated_total_minor=amount, submitted_at=now,
            estimated_cost=json.dumps({"staff_claim": True, "submitted_at": now.isoformat()}))
        ctx.audit("event.reimbursement.staff_claim_filed", row, request_id=row.pk,
                  on_behalf=registration.member_id != ctx.actor.pk)
        if registration.member_id != ctx.actor.pk:
            from .notices import enqueue_locked
            enqueue_locked(row, "staff_claim_filed")
        return ctx.finish(row, uuid=str(row.uuid))

"""Hack-money G12: travel the organiser books directly for a participant (or crew member).

Finance records the booked cost against the request. In ONE transaction this:
- writes (or replaces an offered) award, state ``closed`` with reason ``direct_booking``;
- reserves and commits that amount from the award's pool (crew requests use the crew pool, G14);
- records the cost as a ledger expense (domain ``events``, category ``travel``), sourced to the award.
The member files no claim and no money is ever sent: the space already paid the vendor. A cash
advance is NOT this (it would weaken #34's "claim after attendance"); see the owner list.

A mistake is cancelled by finance: the ledger expense is voided and the committed budget released.
Event cancellation never touches a direct booking (`deadlines.close_award_locked`).
"""
from decimal import Decimal

from django.utils import timezone

from apps.payments.currencies import supported_minor_unit_exponent
from apps.payments.event_payouts.errors import require
from apps.payments.event_payouts.validation import minor
from .award_models import GrantAward, GrantAwardRevision
from .budget_models import BudgetReservation
from .budget_service import book_directly_locked, release_locked
from .config_models import ReimbursementProgramme
from .pools import lock_pools, pool_for
from .request_models import GrantRequest
from .request_workflow import reviewed_locked
from .transactions import changed, command

SOURCE_KIND = "events.reimbursement_direct_booking"
REASON = "direct_booking"


def major(amount_minor, currency):
    return Decimal(amount_minor) / (Decimal(10) ** supported_minor_unit_exponent(currency))


def _locked(ctx, request_id):
    programme = ReimbursementProgramme.objects.select_for_update().get(event=ctx.event)
    pools = lock_pools(programme)
    row = GrantRequest.objects.select_for_update().get(pk=request_id, programme=programme)
    award = GrantAward.objects.select_for_update().filter(request=row).first()
    return programme, pools, row, award


def record(*, request, event_id, request_id, data):
    from apps.payments.ledger_api import record_expense
    seed = GrantRequest.objects.get(pk=request_id, event_id=event_id)
    amount = minor(data["amount_minor"])
    with command(event_id=event_id, actor=request.user, request=request, data=data,
                 action=f"request.direct_booking:{request_id}", finance=True, account_ids=(seed.member_id,)) as ctx:
        if ctx.replay:
            return ctx.replay
        programme, pools, row, award = _locked(ctx, request_id)
        ctx.cas(row)
        require(data["currency"] == programme.currency, "pool_currency_mismatch", status=400)
        require(row.state in ("requested", "waitlisted", "awarded") and (award is None or award.state == "offered"),
                "accepted_award_immutable")
        require(programme.enabled and ctx.event.status != "cancelled", "reimbursement_unavailable")
        pool = pool_for(pools, programme, row.kind, award)
        require(pool.version == data["expected_pool_version"], "stale_pool_version")
        now = timezone.now()
        values = dict(state="closed", amount_minor=amount, currency=programme.currency,
                      rule_revision=programme.finance_policy_revision, accept_by=now, closed_at=now, reason_code=REASON,
                      calculation_snapshot={"mode": REASON, "vendor": data["vendor"],
                                            "booked_on": data["booked_on"].isoformat()})
        if award:
            changed(award, **values, due_revision=award.due_revision + 1)
        else:
            award = GrantAward.objects.create(request=row, pool=pool, offered_at=now, issued_by=ctx.actor, **values)
        book_directly_locked(pool, award, amount, operation_id=data["operation_id"], actor=ctx.actor)
        GrantAwardRevision.objects.create(award=award, revision=award.version, amount_minor=amount,
                                          rule_snapshot=award.calculation_snapshot, actor=ctx.actor, reason_code=REASON)
        entry = record_expense(ctx.event.makerspace, "events", None, major(amount, programme.currency), programme.currency,
                               data["method"], data.get("reference", ""), data.get("receipt_id"), SOURCE_KIND,
                               str(award.uuid), ctx.actor, category="travel", event=ctx.event,
                               description=f"Travel booked: {ctx.event.title}"[:300], entry_date=data["booked_on"],
                               counterparty=data["vendor"])
        reviewed_locked(ctx, row, state="awarded", reason_code=REASON)
        ctx.audit("event.reimbursement.direct_booking_recorded", award, request_id=row.pk, pool_id=pool.pk,
                  ledger_entry_id=entry.pk)
        return ctx.finish(row, award_id=award.pk, award_version=award.version, pool_version=pool.version,
                          ledger_entry_id=entry.pk)


def cancel(*, request, event_id, request_id, data):
    from apps.payments.ledger_api import void
    from apps.payments.models_ledger_entries import LedgerEntry
    seed = GrantRequest.objects.get(pk=request_id, event_id=event_id)
    with command(event_id=event_id, actor=request.user, request=request, data=data,
                 action=f"request.direct_booking_cancel:{request_id}", finance=True, account_ids=(seed.member_id,)) as ctx:
        if ctx.replay:
            return ctx.replay
        programme, pools, row, award = _locked(ctx, request_id)
        ctx.cas(row)
        require(award is not None and award.state == "closed" and award.reason_code == REASON, "direct_booking_required")
        pool = pools[award.pool_id]
        require(pool.version == data["expected_pool_version"], "stale_pool_version")
        reservation = BudgetReservation.objects.select_for_update().get(award=award, pool=pool)
        release_locked(pool, reservation, operation_id=data["operation_id"], actor=ctx.actor,
                       reason_code="direct_booking_cancelled", cancel_committed=True)
        entry = LedgerEntry.objects.filter(makerspace=ctx.event.makerspace, source_kind=SOURCE_KIND,
                                           source_id=str(award.uuid), voided_at__isnull=True).first()
        if entry is not None:
            void(entry, ctx.actor, data["reason"])
        changed(award, state="forfeited", reason_code="direct_booking_cancelled")
        reviewed_locked(ctx, row, state="declined", reason_code="direct_booking_cancelled")
        ctx.audit("event.reimbursement.direct_booking_cancelled", award, request_id=row.pk, pool_id=pool.pk,
                  ledger_entry_id=entry.pk if entry else None)
        return ctx.finish(row, award_id=award.pk, award_version=award.version, pool_version=pool.version)

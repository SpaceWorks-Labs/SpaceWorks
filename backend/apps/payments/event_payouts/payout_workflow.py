"""Record a completed human payment. This module never initiates a transfer."""
from uuid import uuid4
from django.utils import timezone
from apps.audit.services import record as audit
from .errors import require
from .ledger_math import Entry, validate_append, validate_record_metadata
from .payout_models import EventPayoutEntry
from .payee_workflow import current
from .queries import entries
from .transactions import command


def record(*, request, obligation_id, data):
    return _append(request=request, obligation_id=obligation_id, data=data, entry_id=None)


def amend(*, request, obligation_id, entry_id, data):
    return _append(request=request, obligation_id=obligation_id, data=data, entry_id=entry_id)


def _append(*, request, obligation_id, data, entry_id):
    action = f"payout.amend:{entry_id}" if entry_id else "payout.record"
    with command(request=request, obligation_id=obligation_id, data=data, action=action, payout=True) as ctx:
        from .obligation_models import EventPayoutObligationRevision
        require(not EventPayoutObligationRevision.objects.filter(operation_id=data["operation_id"]).exists(),
                "idempotency_conflict")
        # Durable entry identity survives expiry of ordinary command receipts.
        prior = EventPayoutEntry.objects.filter(operation_id=data["operation_id"]).first()
        if prior:
            require(prior.command_digest == ctx.digest and prior.obligation_id == ctx.obligation.pk
                    and prior.recorded_by_id == ctx.actor.pk, "idempotency_conflict")
            return {"id": str(ctx.obligation.pk), "version": ctx.obligation.version,
                    "state": ctx.obligation.state, "entry_id": str(prior.pk)}
        if ctx.replay:
            return ctx.replay
        ctx.cas()
        row = ctx.obligation
        require(row.state != "cancelled", "obligation_cancelled")
        parent = row.entries.select_for_update().get(pk=entry_id) if entry_id else None
        require(data["currency"] == row.currency, "payout_currency_mismatch", status=400)
        metadata = validate_record_metadata(method=data["method"], payment_reference=data["reference"],
            paid_at=data["paid_at"], now=timezone.now())
        require(data["method"] != "other" or data.get("reason_code"), "other_method_reason_required", status=400)
        if parent:
            require(data.get("reason_code"), "amendment_reason_required", status=400)
            require(not parent.__class__.objects.filter(amends=parent).exists(), "payout_tip_changed")
            require(data["payee_revision"] == parent.payee_revision_id, "amendment_payee_immutable")
            payee = parent.payee_revision
        else:
            require(row.eligibility_status == "eligible" and not row.hold_reason_code, "payout_held")
            require(data["eligibility_revision"] == row.eligibility_revision, "eligibility_changed")
            payee = current(row, lock=True)
            require(payee is not None and payee.pk == data["payee_revision"]
                and payee.state == "current" and payee.verified_at and payee.details
                and payee.method == data["method"] and payee.version == data["expected_payee_version"], "payee_not_ready")
        candidate = Entry(id=uuid4(), obligation_id=row.pk, chain_uuid=parent.chain_uuid if parent else uuid4(),
            currency=row.currency, amount_minor=data["amount_minor"], amends_id=parent.pk if parent else None,
            is_void=data.get("is_void", False))
        paid = validate_append(entries(row), candidate, approved_minor=row.approved_minor)
        entry = EventPayoutEntry.objects.create(id=candidate.id, obligation=row, payee_revision=payee,
            eligibility_revision=row.eligibility_revision, amount_minor=candidate.amount_minor, currency=row.currency,
            recorded_by=ctx.actor, operation_id=data["operation_id"], command_digest=ctx.digest,
            chain_uuid=candidate.chain_uuid, amends=parent, reason_code=data.get("reason_code", ""),
            is_void=candidate.is_void, **metadata)
        from .obligation_workflow import project_settlement_locked
        project_settlement_locked(row, effective_paid=paid, operation_id=data["operation_id"])
        audit(ctx.actor, "finance.event_payout.amended" if parent else "finance.event_payout.recorded",
            makerspace=row.makerspace, target=entry, meta={"obligation_id": str(row.pk),
                "entry_id": str(entry.pk), "amount_minor": entry.amount_minor, "currency": row.currency,
                "amends_id": str(parent.pk) if parent else None})
        return ctx.finish(entry_id=str(entry.pk))

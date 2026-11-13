"""Permanent liability state, settlement projection and durable unpaid cancellation."""
from django.utils import timezone
from apps.audit.services import record
from .errors import require
from .obligation_models import EventPayoutObligation, EventPayoutObligationRevision
from .queries import paid
from .transactions import command
from .wire import command_digest, cancellation_command
from .decision_workflow import create_locked, correct_locked


def project_settlement_locked(obligation, *, effective_paid, operation_id):
    from .attachment_workflow import close_binding_locked, reopen_locked
    from .payee_workflow import close_locked
    require(0 <= effective_paid <= obligation.approved_minor and obligation.state != "cancelled", "payout_exceeds_approval")
    old_state = obligation.state
    settled = effective_paid == obligation.approved_minor
    if settled and obligation.terminal_financial_at is None:
        obligation.terminal_financial_at = timezone.now()
        close_locked(obligation, terminal_at=obligation.terminal_financial_at, reason_code="fully_paid")
        close_binding_locked(makerspace_id=obligation.makerspace_id, obligation=obligation,
            terminal_at=obligation.terminal_financial_at, reason_code="fully_paid", operation_id=operation_id)
    elif not settled and obligation.terminal_financial_at is not None:
        obligation.terminal_financial_at = None
        # Purged values stay empty; only future collection can replace them.
        for row in obligation.payee_revisions.select_for_update().exclude(state="purged").order_by("pk"):
            if row.state != "current" and not row.entries.exists():
                continue
            row.terminal_financial_at = row.purge_due_at = row.paid_closed_at = None
            row.closure_reason_code, row.version = "", row.version + 1
            row.save(update_fields=["terminal_financial_at", "purge_due_at", "paid_closed_at", "closure_reason_code", "version"])
            record(None, "finance.event_payout.payee_reopened", makerspace=obligation.makerspace, target=row,
                   meta={"payee_revision_id": str(row.pk)})
        reopen_locked(obligation)
    obligation.state, obligation.version = ("settled" if settled else "open"), obligation.version + 1
    obligation.save()
    record(None, "finance.event_payout.settlement_projected", makerspace=obligation.makerspace, target=obligation,
        meta={"old_state": old_state, "new_state": obligation.state, "effective_paid_minor": effective_paid,
              "operation_id": str(operation_id)})


def cancel_unpaid(*, request, obligation_id, data):
    from .attachment_workflow import close_binding_locked
    from .payee_workflow import close_locked
    from .coordination import prepare
    from .authority import authorize
    from .payout_models import EventPayoutEntry
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    data = {**data, **cancellation_command(data)}
    seed = EventPayoutObligation.objects.select_related("makerspace").get(pk=obligation_id)
    authorize(request, seed.makerspace, mutation=True)
    assert_write_allowed(seed.makerspace_id)
    require(request.headers.get("Idempotency-Key") == str(data["operation_id"]), "idempotency_key_mismatch", status=400)
    digest = command_digest("obligation.cancel", seed.pk, data)
    durable = EventPayoutObligationRevision.objects.filter(operation_id=data["operation_id"]).first()
    if durable:
        require(durable.obligation_id == seed.pk and durable.command_digest == digest
                and durable.actor_id == request.user.pk and durable.kind == "cancellation", "idempotency_conflict")
        return {"id": str(seed.pk), "version": seed.version, "state": seed.state,
            "cancellation_revision_id": durable.pk, "sequence": durable.sequence,
            "terminal_financial_at": seed.terminal_financial_at.isoformat() if seed.terminal_financial_at else None}
    require(not EventPayoutEntry.objects.filter(operation_id=data["operation_id"]).exists(), "idempotency_conflict")
    prefix = prepare(seed)
    with command(request=request, obligation_id=obligation_id, data=data, action="obligation.cancel", prefix=prefix) as ctx:
        row = ctx.obligation
        prior = EventPayoutObligationRevision.objects.filter(operation_id=data["operation_id"]).first()
        if prior:
            require(prior.obligation_id == row.pk and prior.command_digest == ctx.digest
                    and prior.actor_id == ctx.actor.pk and prior.kind == "cancellation", "idempotency_conflict")
            return {"id": str(row.pk), "version": row.version, "state": row.state,
                "cancellation_revision_id": prior.pk, "sequence": prior.sequence,
                "terminal_financial_at": row.terminal_financial_at.isoformat() if row.terminal_financial_at else None}
        if ctx.replay:
            return ctx.replay
        ctx.cas()
        require(row.domain_coordination_state == seed.domain_coordination_state, "payout_coordination_changed")
        require(row.state != "cancelled", "obligation_cancelled")
        require(row.state == "open" and paid(row) == 0, "obligation_already_paid")
        # Lock all payee parents before payout tips and attachment children.
        list(row.payee_revisions.select_for_update().order_by("pk"))
        previous = row.current_revision
        require(previous is not None and previous.sequence == data["expected_revision_sequence"], "stale_decision_sequence")
        require((prefix is not None) == (data["expected_pool_version"] is not None), "invalid_pool_version", status=400)
        if prefix:
            prefix.recheck_locked(obligation=row, expected_pool_version=data["expected_pool_version"])
        revision = EventPayoutObligationRevision.objects.create(obligation=row, sequence=previous.sequence + 1,
            previous_revision=previous, kind="cancellation", approved_minor=0, currency=row.currency, actor=ctx.actor,
            decision_uuid=None, decision_revision=None, reason_code=data["reason_code"], cancellation_note=data["note"],
            operation_id=data["operation_id"], command_digest=ctx.digest,
            decision_summary_schema_version=previous.decision_summary_schema_version, decision_summary=previous.decision_summary)
        terminal = timezone.now()
        row.approved_minor, row.current_revision, row.state = 0, revision, "cancelled"
        row.terminal_financial_at, row.version = terminal, row.version + 1
        row.save()
        if prefix:
            prefix.close_locked(obligation=row, revision=revision, actor=ctx.actor, operation_id=data["operation_id"])
        close_locked(row, terminal_at=terminal, reason_code="finance_cancelled")
        close_binding_locked(makerspace_id=row.makerspace_id, obligation=row, terminal_at=terminal,
            reason_code="finance_cancelled", operation_id=data["operation_id"])
        record(ctx.actor, "finance.event_payout.cancelled", makerspace=row.makerspace, target=row,
            meta={"obligation_id": str(row.pk), "revision_id": revision.pk, "reason_code": data["reason_code"],
                  "old_state": "open", "new_state": "cancelled"})
        from .notices import enqueue_locked
        enqueue_locked(row, "cancelled")
        return ctx.finish(cancellation_revision_id=revision.pk, sequence=revision.sequence,
                          terminal_financial_at=terminal.isoformat())

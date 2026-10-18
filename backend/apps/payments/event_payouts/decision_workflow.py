"""Internal liability port; domain decision/budget/summary commit in one transaction.

Call only after source, crypto, account, event, host/authority and domain parent
locks. No authorization or domain lookup is delegated back out of a core lock.
"""
from uuid import UUID
from django.db import connection, transaction
from apps.audit.services import record
from apps.encryption.account_write_fence import assert_account_fence_held
from .errors import require
from .decision_snapshots import validate_summary
from .obligation_models import EventPayoutObligation, EventPayoutObligationRevision
from .payout_models import EventPayoutEntry
from .queries import paid
from .wire import canonical, fingerprint


def create_locked(*, makerspace, event, owner, actor, operation_id, decision_summary,
                  expected_version=0, expected_revision_sequence=0):
    require(connection.in_atomic_block, "locked_transaction_required")
    assert_account_fence_held(actor.pk)
    if owner is not None:
        assert_account_fence_held(owner.pk)
    snapshot = validate_summary(decision_summary)
    require(snapshot["decision"]["actor_id"] == actor.pk, "decision_actor_mismatch")
    require(event.makerspace_id == makerspace.pk and owner is not None
        and owner.account_kind == "member", "decision_scope_mismatch")
    operation_id = UUID(str(operation_id))
    source_uuid = UUID(snapshot["source"]["claim_uuid"])
    digest = fingerprint({"source_uuid": source_uuid, "event_id": event.pk,
        "makerspace_id": makerspace.pk, "owner_id": owner.pk, "summary": snapshot,
        "expected_version": expected_version, "expected_revision_sequence": expected_revision_sequence})
    # Caller holds the source claim mutex, including for first insertion.
    with transaction.atomic():
        row = EventPayoutObligation.objects.select_for_update().filter(
            source_kind="event_reimbursement", source_uuid=source_uuid).first()
        prior = EventPayoutObligationRevision.objects.filter(operation_id=operation_id).first()
        if prior:
            require(row is not None and prior.obligation_id == row.pk and prior.kind == "decision"
                and prior.command_digest == digest and prior.actor_id == actor.pk, "idempotency_conflict")
            return row
        require(not EventPayoutEntry.objects.filter(operation_id=operation_id).exists(), "idempotency_conflict")
        if row is None:
            require(expected_version == expected_revision_sequence == 0, "stale_version")
            require(snapshot["totals"]["approved_minor"] > 0, "positive_liability_required")
            row = EventPayoutObligation.objects.create(makerspace=makerspace, owner_member=owner, event=event,
                event_id_snapshot=event.pk, event_title_snapshot=event.title, source_uuid=source_uuid,
                source_decision_revision=snapshot["source"]["decision_sequence"],
                currency=snapshot["award"]["currency"], approved_minor=snapshot["totals"]["approved_minor"])
        else:
            require(row.makerspace_id == makerspace.pk and row.owner_member_id == owner.pk
                and row.event_id_snapshot == event.pk and row.currency == snapshot["award"]["currency"],
                "decision_scope_mismatch")
            require(row.state != "cancelled" and row.domain_coordination_state == "attached", "obligation_cancelled")
            require(row.version == expected_version and row.current_revision is not None
                and row.current_revision.sequence == expected_revision_sequence, "stale_version")
            require(snapshot["source"]["decision_sequence"] > row.source_decision_revision, "stale_decision_sequence")
            require(snapshot["totals"]["approved_minor"] >= paid(row), "decision_below_paid")
        # Payees precede attachment/allocation children in the published lock order.
        list(row.payee_revisions.select_for_update().order_by("pk"))
        from .decision_bindings import validate_locked
        validate_locked(snapshot=snapshot, obligation=row)
        previous = row.current_revision
        revision = EventPayoutObligationRevision.objects.create(obligation=row,
            sequence=previous.sequence + 1 if previous else 1, previous_revision=previous,
            kind="decision", approved_minor=snapshot["totals"]["approved_minor"], currency=row.currency,
            actor=actor, decision_uuid=UUID(snapshot["source"]["decision_uuid"]),
            decision_revision=snapshot["source"]["decision_sequence"], reason_code=snapshot["decision"]["reason_code"],
            cancellation_note="", operation_id=operation_id, command_digest=digest,
            decision_summary_schema_version=1, decision_summary=canonical(snapshot))
        row.approved_minor, row.current_revision = revision.approved_minor, revision
        row.source_decision_revision = revision.decision_revision
        # A financial approval pins the exact evidence; G's canonical bridge must
        # publish a fresh fact before any new payment can pass preflight.
        row.eligibility_evidence = snapshot["eligibility"]
        row.eligibility_status = "needs_acknowledgement"
        row.eligibility_revision += 1
        require(snapshot["eligibility"]["core_eligibility_revision"] == row.eligibility_revision,
                "decision_eligibility_revision_mismatch")
        from .eligibility_models import PayoutEligibility
        PayoutEligibility.objects.create(obligation=row, evidence_revision=row.eligibility_revision,
            evidence=snapshot["eligibility"], status="needs_acknowledgement", reason_code="decision_recorded")
        row.save()
        from .attachment_workflow import bind_claim_locked
        from .obligation_workflow import project_settlement_locked
        bind_claim_locked(obligation=row, claim_uuid=source_uuid)
        project_settlement_locked(row, effective_paid=paid(row), operation_id=operation_id)
        record(actor, "finance.event_payout.decision_recorded", makerspace=makerspace, target=row,
            meta={"obligation_id": str(row.pk), "revision_id": revision.pk, "sequence": revision.sequence,
                  "approved_minor": row.approved_minor, "currency": row.currency})
        from .notices import enqueue_locked
        enqueue_locked(row, "approved" if previous is None else "decision_corrected")
        return row


def correct_locked(**kwargs):
    require(kwargs.get("expected_version", 0) > 0, "stale_version")
    return create_locked(**kwargs)

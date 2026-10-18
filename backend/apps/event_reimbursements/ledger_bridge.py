"""Only this domain-to-core adapter calls the permanent obligation writer."""
from uuid import uuid4
from apps.payments.event_payouts.obligation_models import EventPayoutObligation
from apps.payments.event_payouts.queries import paid
from apps.payments.event_payouts.errors import require


def lock_obligation(claim, *, expected_version):
    row = EventPayoutObligation.objects.select_for_update().filter(
        makerspace_id=claim.event.makerspace_id, source_kind="event_reimbursement", source_uuid=claim.uuid).first()
    require(expected_version == (row.version if row else None), "stale_obligation_version")
    require(row is None or paid(row) == 0, "claim_already_paid")
    require(row is None or row.state != "cancelled", "obligation_cancelled")
    return row


def preserve_locked(*, ctx, claim, decision, summary, attendance, existing):
    from apps.payments.event_payouts.obligation_workflow import create_locked
    # Model-free arguments: core must never import an Events/R service or row.
    return create_locked(makerspace=ctx.event.makerspace, actor=ctx.actor,
        obligation_id=decision.core_obligation_id, owner_member_id=claim.member_id,
        event_id=ctx.event.pk, event_title=ctx.event.title, source_uuid=claim.uuid,
        decision_uuid=decision.uuid, decision_sequence=decision.sequence,
        approved_minor=decision.approved_total_minor, currency=decision.currency,
        summary=summary, eligibility_evidence=attendance, operation_id=ctx.data["operation_id"],
        command_digest=ctx.digest, expected_version=existing.version if existing else None)

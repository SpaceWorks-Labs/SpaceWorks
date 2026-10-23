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


def next_core_eligibility_revision(existing):
    """Core bumps the obligation's eligibility revision once per decision; match it."""
    if existing is not None:
        return existing.eligibility_revision + 1
    return EventPayoutObligation._meta.get_field("eligibility_revision").get_default() + 1


def preserve_locked(*, ctx, claim, decision, summary, attendance, existing):
    from apps.payments.event_payouts.decision_workflow import create_locked
    # Core receives rows and the frozen G1 summary only; it never imports an Events/R service.
    return create_locked(makerspace=ctx.event.makerspace, event=ctx.event, owner=claim.member, actor=ctx.actor,
        operation_id=ctx.data["operation_id"], decision_summary=summary, obligation_id=decision.core_obligation_id,
        expected_version=existing.version if existing else 0,
        expected_revision_sequence=existing.current_revision.sequence if existing else 0)

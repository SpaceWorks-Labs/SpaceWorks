"""Safe ledger projections; payee payloads have a separate audited access path."""
from .ledger_math import Entry, effective_paid


def entries(obligation):
    return tuple(Entry(id=row.pk, obligation_id=row.obligation_id, chain_uuid=row.chain_uuid,
        currency=row.currency, amount_minor=row.amount_minor, amends_id=row.amends_id,
        is_void=row.is_void) for row in obligation.entries.order_by("recorded_at", "pk"))


def paid(obligation):
    return effective_paid(entries(obligation), obligation_id=obligation.pk,
                          currency=obligation.currency, approved_minor=obligation.approved_minor)


def summary(obligation):
    amount = paid(obligation)
    return {"id": str(obligation.pk), "version": obligation.version,
        "event_id": obligation.event_id_snapshot, "event_title": obligation.event_title_snapshot,
        "currency": obligation.currency, "approved_minor": obligation.approved_minor,
        "effective_paid_minor": amount, "remaining_minor": obligation.approved_minor - amount,
        "state": obligation.state, "eligibility_status": obligation.eligibility_status,
        "eligibility_revision": obligation.eligibility_revision,
        "current_revision_sequence": obligation.current_revision.sequence if obligation.current_revision_id else None,
        "coordination_state": obligation.domain_coordination_state}

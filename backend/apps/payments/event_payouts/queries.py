"""Safe ledger projections; payee payloads have a separate audited access path."""
from .ledger_math import Entry, effective_paid


def entries(obligation):
    return tuple(Entry(id=row.pk, obligation_id=row.obligation_id, chain_uuid=row.chain_uuid,
        currency=row.currency, amount_minor=row.amount_minor, amends_id=row.amends_id,
        is_void=row.is_void) for row in obligation.entries.order_by("recorded_at", "pk"))


def paid(obligation):
    return effective_paid(entries(obligation), obligation_id=obligation.pk,
                          currency=obligation.currency, approved_minor=obligation.approved_minor)


def summary(obligation, *, request=None, owner=False):
    amount = paid(obligation)
    return {"id": str(obligation.pk), "version": obligation.version,
        "event_id": obligation.event_id_snapshot, "event_title": obligation.event_title_snapshot,
        "currency": obligation.currency, "approved_minor": obligation.approved_minor,
        "effective_paid_minor": amount, "remaining_minor": obligation.approved_minor - amount,
        "state": obligation.state, "eligibility_status": obligation.eligibility_status,
        "eligibility_revision": obligation.eligibility_revision,
        "current_revision_sequence": obligation.current_revision.sequence if obligation.current_revision_id else None,
        "coordination_state": obligation.domain_coordination_state,
        "allowed_actions": allowed_actions(obligation, request=request, owner=owner, effective_paid=amount)}


def allowed_actions(obligation, *, request, owner=False, effective_paid=None):
    if request is None:
        return []
    from .payee_workflow import current
    payee = current(obligation)
    if owner:
        actions = ["read"]
        if obligation.state == "open" and obligation.approved_minor > 0:
            actions.append("payee_submit")
        if payee is not None:
            actions.append("payee_reveal")
        return actions
    from apps.accounts import rbac
    from .eligibility_workflow import active_holds
    actions = ["read", "hold", "release_hold"]
    if payee is not None:
        actions.append("payee_reveal")
    ready = (payee is not None and payee.verified_at and obligation.eligibility_status == "eligible"
             and not obligation.hold_reason_code and not active_holds(obligation).exists())
    if obligation.state == "open":
        actions.append("acknowledge_eligibility")
        if payee is not None:
            actions += ["payee_verify", "payee_request_correction"]
        if (effective_paid if effective_paid is not None else paid(obligation)) == 0:
            actions.append("cancel_unpaid")
        if ready:
            actions.append("masked_export")
    if rbac.can(request.user, rbac.Action.RECORD_REIMBURSEMENT_PAYOUT, obligation.makerspace_id):
        if obligation.state == "open" and ready:
            actions.append("record")
        if obligation.state != "cancelled" and obligation.entries.exists():
            actions.append("amend")
    return actions

"""Optional live evidence refresh, completed BEFORE the core payout transaction."""
from uuid import uuid4
from apps.payments.event_payouts.errors import require
from apps.payments.event_payouts.obligation_models import EventPayoutObligation
from apps.payments.event_payouts.eligibility_workflow import publish_locked
from .attendance import evidence, participating
from .eligibility import project_evidence
from .claim_models import ReimbursementClaim
from .transactions import command


def current_evidence(*, claim, programme):
    value = evidence(claim=claim, programme=programme, enforce=False)
    from apps.payments.event_payouts.errors import PayoutError
    project_valid = True
    try:
        project = project_evidence(claim=claim, programme=programme)
    except PayoutError as exc:
        if exc.detail.get("code") != "project_submission_required":
            raise
        project, project_valid = None, False
    value.update(project_snapshot_ref=str(project.reference) if project else None,
        project_snapshot_id=project.snapshot_id if project else None,
        event_cancelled=claim.event.status == "cancelled",
        participation_valid=participating(claim.award.request))
    value["eligible"] = value["eligible"] and project_valid and value["participation_valid"] and not value["event_cancelled"]
    return value


def _unchanged(stored, facts):
    """Stored evidence is either the decision's G1 block or a published Facts dict."""
    def strip(evidence):
        return {key: value for key, value in evidence.items() if key != "core_eligibility_revision"}
    if isinstance(stored, dict) and "evidence" in stored:
        current = facts.as_dict()
        return {**stored, "evidence": strip(stored["evidence"])} == {**current, "evidence": strip(current["evidence"])}
    return False


def publish_claim_locked(*, claim, programme, actor):
    """G invokes after canonical attendance/correction, while event/parents lock."""
    obligation = EventPayoutObligation.objects.select_for_update().filter(source_uuid=claim.uuid,
        source_kind="event_reimbursement", makerspace_id=claim.event.makerspace_id).first()
    if obligation is None:
        return None
    from .payout_facts import facts_for
    facts = facts_for(claim=claim, programme=programme, obligation=obligation)
    if not _unchanged(obligation.eligibility_evidence, facts):
        publish_locked(obligation, evidence_revision=obligation.eligibility_revision + 1, evidence=facts.as_dict(),
            eligible=facts.eligible, reason_code="attendance_current" if facts.eligible else "attendance_invalidated", actor=actor)
        if not facts.eligible:
            from apps.payments.event_payouts.eligibility_workflow import hold_for_domain_review_locked
            hold_for_domain_review_locked(obligation, actor=actor, operation_id=uuid4(), reason_code="attendance_invalidated")
    return {"eligibility_revision": obligation.eligibility_revision, "status": obligation.eligibility_status}


def refresh(*, request, obligation_id):
    """No callback from a held core lock into this function is permitted."""
    from .claim_workflow import lock_claim_parents
    seed = EventPayoutObligation.objects.get(pk=obligation_id)
    claim = ReimbursementClaim.objects.get(uuid=seed.source_uuid, event__makerspace_id=seed.makerspace_id)
    with command(event_id=claim.event_id, actor=request.user, request=request,
        data={"operation_id": uuid4(), "expected_version": 0}, action="payout.preflight", finance=True,
        account_ids=(claim.member_id,)) as ctx:
        programme, _, _, locked = lock_claim_parents(ctx.event, claim_id=claim.pk)
        return publish_claim_locked(claim=locked, programme=programme, actor=ctx.actor)

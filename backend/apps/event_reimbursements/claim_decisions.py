"""Final finance decisions coordinate pool, immutable evidence and core liability."""
from datetime import timedelta
from uuid import uuid4
from django.utils import timezone
from apps.payments.event_payouts.errors import require
from .award_models import GrantAward
from .budget_models import BudgetReservation
from .budget_service import commit_locked
from .claim_decision_models import ClaimDecision, ClaimLineDecision, ClaimAppeal
from .claim_policy import validate_decisions
from .attendance import evidence, participating
from .eligibility import project_evidence
from .decision_summary import build
from .ledger_bridge import lock_obligation, preserve_locked
from .transactions import command, changed
from .notices import enqueue_locked


def decide(*, request, event_id, claim_id, data, correction=False):
    from .claim_workflow import lock_claim_parents
    from .claim_finality import finalize_terminal_locked
    from .claim_models import ReimbursementClaim
    seed = ReimbursementClaim.objects.get(pk=claim_id, event_id=event_id)
    with command(event_id=event_id, actor=request.user, request=request, data=data,
        action=f"claim.{'correct' if correction else 'decide'}:{claim_id}", finance=True,
        account_ids=(seed.member_id,)) as ctx:
        if ctx.replay:
            return ctx.replay
        programme, pool, award, claim = lock_claim_parents(ctx.event, claim_id=claim_id)
        ctx.cas(claim)
        require(pool.version == data["expected_pool_version"], "stale_pool_version")
        require(claim.current_revision_id == data["claim_revision_id"], "stale_claim_revision")
        sequence = claim.decisions.count() + 1
        require(data["expected_decision_sequence"] == sequence - 1, "stale_decision_sequence")
        terminal = ("approved", "partially_approved", "rejected")
        require(claim.state in terminal if correction else claim.state in ("submitted", "under_review"), "claim_not_reviewable")
        require(ctx.event.status != "cancelled", "event_cancelled")
        require(data["outcome"] in (*terminal, "returned_for_info") and
                (not correction or data["outcome"] in terminal), "invalid_outcome", status=400)
        lines = list(claim.current_revision.lines.order_by("line_uuid"))
        reservation = BudgetReservation.objects.select_for_update().get(award=award, pool=pool)
        attendance = evidence(claim=claim, programme=programme, enforce=data["outcome"] not in ("rejected", "returned_for_info"))
        require(data["eligibility_revision"] == attendance["attendance_revision"], "eligibility_changed")
        project = project_evidence(claim=claim, programme=programme) if data["outcome"] not in ("rejected", "returned_for_info") else None
        if data["outcome"] not in ("rejected", "returned_for_info"):
            require(participating(award.request), "participation_not_accepted")
        attendance.update(project_snapshot_ref=str(project.reference) if project else None,
            project_snapshot_id=project.snapshot_id if project else None, event_cancelled=False,
            participation_valid=True)
        existing = lock_obligation(claim, expected_version=data["expected_obligation_version"])
        if data["outcome"] == "returned_for_info":
            approved = 0
            require(not data["line_decisions"] and data.get("info_due_at") is not None
                and data["info_due_at"] > timezone.now(), "information_deadline_required", status=400)
        else:
            approved = validate_decisions(lines=lines, decisions=data["line_decisions"], award=award, outcome=data["outcome"])
            # A partial decision released the unused cap. An appeal/correction may
            # increase it only from a funded hold or currently free pool capacity.
            require(approved <= reservation.committed_minor + reservation.held_minor +
                pool.total_minor - pool.reserved_minor - pool.committed_minor, "budget_exhausted")
        obligation_id = existing.pk if existing else uuid4() if approved else None
        core_sequence = existing.current_revision.sequence + 1 if existing else 1
        decision = ClaimDecision.objects.create(claim=claim, revision=claim.current_revision, sequence=sequence,
            actor=ctx.actor, outcome=data["outcome"], approved_total_minor=approved, award_minor=award.amount_minor,
            currency=award.currency, attendance_checkin_event_id=attendance["checkin_ids"][-1] if attendance["checkin_ids"] else None,
            attendance_revision=attendance["attendance_revision"], project_snapshot_ref=project.reference if project else None,
            decided_at=timezone.now(), reason_code=data["reason_code"], reason=data.get("note", ""),
            core_obligation_id=obligation_id if data["outcome"] != "returned_for_info" else None,
            core_decision_revision=core_sequence if obligation_id and data["outcome"] != "returned_for_info" else None)
        by_id = {str(row.line_uuid): row for row in lines}
        entries = [ClaimLineDecision.objects.create(decision=decision, line=by_id[str(item["line_uuid"])],
            approved_minor=item["approved_minor"], reason_code=item["reason_code"], reason=item.get("reason", ""))
            for item in data["line_decisions"]]
        old = claim.state
        if data["outcome"] == "returned_for_info":
            changed(claim, state="returned_for_info", current_decision=decision,
                info_due_at=data["info_due_at"], due_revision=claim.due_revision + 1)
        else:
            commit_locked(pool, reservation, approved, operation_id=data["operation_id"], actor=ctx.actor,
                          reason_code=data["reason_code"], decision=decision)
            if obligation_id:
                summary = build(claim=claim, decision=decision, line_decisions=entries,
                    attendance=attendance, eligibility_revision=max(1, (existing.eligibility_revision + 1) if existing else 1))
                preserve_locked(ctx=ctx, claim=claim, decision=decision, summary=summary, attendance=attendance, existing=existing)
            changed(award, state="closed", closed_at=timezone.now(), reason_code="claim_decided")
            appeal_due = decision.decided_at + timedelta(days=7) if data["outcome"] in ("rejected", "partially_approved") else None
            changed(claim, state=data["outcome"], current_decision=decision, info_due_at=None,
                appeal_due_at=appeal_due, domain_closed_at=None, domain_closure_reason_code="")
            appeal = ClaimAppeal.objects.select_for_update().filter(claim=claim, resolution_at__isnull=True).first()
            if appeal:
                appeal.resolved_decision, appeal.resolution_at = decision, timezone.now()
                appeal.save(update_fields=["resolved_decision", "resolution_at"])
            finalize_terminal_locked(ctx, claim, force=claim.appeal_used or data["outcome"] == "approved")
        ctx.audit("event.reimbursement.claim_decision_corrected" if correction else "event.reimbursement.claim_decided",
            claim, decision_id=decision.pk, old_state=old, new_state=claim.state, reason_code=data["reason_code"])
        enqueue_locked(claim, "returned_for_info" if data["outcome"] == "returned_for_info" else "decision")
        from .work_items import schedule_claim_locked
        schedule_claim_locked(claim)
        return ctx.finish(claim, decision_id=decision.pk, decision_sequence=decision.sequence,
            obligation_id=str(obligation_id) if obligation_id else None, pool_version=pool.version)

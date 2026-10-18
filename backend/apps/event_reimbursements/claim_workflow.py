"""Claim state entrypoint. Financial decisions append separately under its locks."""
import json
from datetime import timedelta
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
from apps.events.staged_forms.guards import require_complete_locked
from apps.events.staged_forms.trigger_service import resolve_participant
from apps.payments.currencies import supported_minor_unit_exponent
from apps.payments.event_payouts.errors import require
from apps.payments.event_payouts.obligation_models import EventPayoutObligation
from apps.payments.event_payouts.queries import paid
from .award_models import GrantAward
from .budget_models import ReimbursementBudgetPool, BudgetReservation
from .config_models import ReimbursementProgramme
from .request_models import GrantRequest
from .claim_models import ReimbursementClaim
from .claim_revision_models import ClaimRevision, ClaimLine
from .claim_decision_models import ClaimAppeal, ClaimScreeningReview
from .claim_inputs import ClaimDraftInput
from .transactions import command, changed
from .calculations import convert_minor
from .attendance import evidence


def lock_claim_parents(event, claim_id=None, owner_id=None):
    programme = ReimbursementProgramme.objects.select_for_update().get(event=event)
    pool = ReimbursementBudgetPool.objects.select_for_update().get(programme=programme, currency=programme.currency)
    seed = ReimbursementClaim.objects.get(pk=claim_id, event=event) if claim_id else None
    grant = GrantRequest.objects.select_for_update().get(programme=programme, **(
        {"award__pk": seed.award_id} if seed else {"member_id": owner_id}))
    award = GrantAward.objects.select_for_update().get(request=grant, pool=pool)
    claim = ReimbursementClaim.objects.select_for_update().filter(award=award).first()
    return programme, pool, award, claim


def save_draft(*, event_id, actor, data):
    serializer = ClaimDraftInput(data={"lines": data["lines"]})
    serializer.is_valid(raise_exception=True)
    with command(event_id=event_id, actor=actor, data=data, action="claim.draft", owner=True) as ctx:
        if ctx.replay:
            return ctx.replay
        programme, pool, award, claim = lock_claim_parents(ctx.event, owner_id=actor.pk)
        require(award.state == "accepted" and ctx.event.ends_at <= timezone.now() < programme.claim_due_at, "claim_closed")
        require(data["expected_version"] == (claim.version if claim else 0), "stale_version")
        if claim is None:
            claim = ReimbursementClaim(award=award, event=ctx.event, member=ctx.actor, effective_due_at=programme.claim_due_at)
        require(claim.state in ("draft", "open", "returned_for_info"), "claim_not_editable")
        claim.draft_payload = json.dumps(serializer.validated_data, cls=DjangoJSONEncoder)
        if claim.pk:
            claim.version += 1
        claim.save()
        ctx.audit("event.reimbursement.claim_draft_saved", claim, claim_id=claim.pk)
        return ctx.finish(claim, uuid=str(claim.uuid))


def submit(*, event_id, actor, data):
    from .receipt_service import pin_receipts_locked
    with command(event_id=event_id, actor=actor, data=data, action="claim.submit", owner=True) as ctx:
        if ctx.replay:
            return ctx.replay
        programme, pool, award, claim = lock_claim_parents(ctx.event, owner_id=actor.pk)
        require(claim is not None, "claim_draft_required")
        ctx.cas(claim)
        require(claim.state in ("draft", "open", "returned_for_info") and award.state == "accepted", "claim_closed")
        due = claim.info_due_at if claim.state == "returned_for_info" else claim.effective_due_at
        require(ctx.event.ends_at <= timezone.now() < due, "claim_closed")
        require_complete_locked(resolve_participant(event=ctx.event, owner_id=actor.pk), "claim_submit")
        attendance = evidence(claim=claim, programme=programme)
        serializer = ClaimDraftInput(data=json.loads(claim.draft_payload))
        serializer.is_valid(raise_exception=True)
        lines = serializer.validated_data["lines"]
        require(not programme.require_project_submission, "project_evidence_provider_required", status=503)
        assets, uses = pin_receipts_locked(claim=claim, lines=lines)
        values, total = [], 0
        for line in lines:
            require(line["category"] in programme.allowed_categories, "claim_category_ineligible", status=400)
            source = line["original_currency"]
            require(source != programme.currency or line["fx_rate"] in ("1", "1.0", "1.00"), "same_currency_fx_invalid", status=400)
            converted = convert_minor(original_minor=line["original_amount_minor"], rate=line["fx_rate"],
                source_exponent=supported_minor_unit_exponent(source), target_exponent=supported_minor_unit_exponent(programme.currency))
            asset = assets[line["line_uuid"]]
            row = {key: value for key, value in line.items() if key != "receipt"}
            row["route"] = json.dumps(row["route"])
            values.append({**row, "converted_minor": converted, "finance_asset": asset, "receipt_hash": asset.sha256})
            total += converted
        sequence = (claim.revisions.order_by("revision").last().revision if claim.revisions.exists() else 0) + 1
        revision = ClaimRevision.objects.create(claim=claim, revision=sequence, submitted_by=ctx.actor,
            submitted_at=timezone.now(), currency=programme.currency, total_minor=total)
        for value in values:
            ClaimLine.objects.create(revision=revision, **value)
        from apps.payments.event_payouts.attachment_workflow import attach_locked
        for asset in {row.pk: row for row in assets.values()}.values():
            attach_locked(asset, binding_uuid=claim.uuid, owner_id=claim.member_id)
        old = claim.state
        changed(claim, current_revision=revision, submitted_at=revision.submitted_at, state="submitted")
        ctx.audit("event.reimbursement.claim_submitted", claim, old_state=old, new_state=claim.state,
                  claim_revision_id=revision.pk, attendance_revision=attendance["attendance_revision"])
        return ctx.finish(claim, claim_revision_id=revision.pk)


def appeal(*, event_id, actor, data):
    with command(event_id=event_id, actor=actor, data=data, action="claim.appeal", owner=True) as ctx:
        if ctx.replay:
            return ctx.replay
        programme, pool, award, claim = lock_claim_parents(ctx.event, owner_id=actor.pk)
        require(claim is not None, "claim_not_found", status=404)
        ctx.cas(claim)
        require(claim.state in ("rejected", "partially_approved") and not claim.appeal_used
                and claim.appeal_due_at and timezone.now() < claim.appeal_due_at, "appeal_closed")
        obligation = EventPayoutObligation.objects.select_for_update().filter(source_uuid=claim.uuid).first()
        require(obligation is None or obligation.state != "cancelled" and paid(obligation) == 0, "claim_already_paid")
        require(data["current_revision"] == claim.current_revision_id, "stale_claim_revision")
        row = ClaimAppeal.objects.create(claim=claim, submitted_by=ctx.actor, submitted_at=timezone.now(),
            statement=data["statement"], original_decision=claim.current_decision)
        changed(claim, state="under_review", appeal_used=True)
        ctx.audit("event.reimbursement.claim_appealed", claim, appeal_id=row.pk)
        return ctx.finish(claim, appeal_id=row.pk)


def recommend(*, event_id, actor, claim_id, data):
    seed = ReimbursementClaim.objects.get(pk=claim_id, event_id=event_id)
    with command(event_id=event_id, actor=actor, data=data, action=f"claim.recommend:{claim_id}",
                 permission="review_reimbursements", account_ids=(seed.member_id,)) as ctx:
        if ctx.replay:
            return ctx.replay
        _, _, _, claim = lock_claim_parents(ctx.event, claim_id=claim_id)
        ctx.cas(claim)
        require(claim.current_revision_id == data["claim_revision_id"], "stale_claim_revision")
        row = ClaimScreeningReview.objects.create(claim=claim, revision=claim.current_revision,
            reviewer=ctx.actor, submitted_at=timezone.now(), recommendation=data["recommendation"],
            reason_code=data["reason_code"], note=data.get("note", ""))
        ctx.audit("event.reimbursement.claim_screened", claim, review_id=row.pk)
        return ctx.finish(claim, review_id=row.pk)


def close_by_cancellation_locked(claim, *, cancellation_revision, terminal_at):
    require(cancellation_revision.obligation.source_uuid == claim.uuid, "invalid_claim_binding")
    claim.domain_closed_at, claim.domain_closure_reason_code = terminal_at, "finance_cancelled"
    claim.version += 1
    claim.save()
    appeal = ClaimAppeal.objects.select_for_update().filter(claim=claim, resolution_at__isnull=True).first()
    if appeal:
        appeal.resolved_by_cancellation_revision_id, appeal.resolution_at = cancellation_revision.pk, terminal_at
        appeal.save(update_fields=["resolved_by_cancellation_revision_id", "resolution_at"])

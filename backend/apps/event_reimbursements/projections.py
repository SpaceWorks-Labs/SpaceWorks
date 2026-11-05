"""Owner/finance evidence is separate from metadata-only screening."""
import json
from django.utils import timezone
from apps.payments.event_payouts.obligation_models import EventPayoutObligation
from apps.payments.event_payouts.queries import summary as payout_summary
from .config_models import ReimbursementProgramme
from .request_models import GrantRequest
from .award_models import GrantAward
from .claim_models import ReimbursementClaim
from .request_form_adapter import context


def pool_detail(pool):
    return {"id": pool.pk, "version": pool.version, "currency": pool.currency, "audience": pool.audience,
        "total_minor": pool.total_minor,
        "reserved_minor": pool.reserved_minor, "committed_minor": pool.committed_minor,
        "available_minor": pool.total_minor - pool.reserved_minor - pool.committed_minor}


def programme_detail(row, *, finance=False):
    if row is None:
        return {"initialized": False}
    value = {"initialized": True, "id": row.pk, "version": row.version, "enabled": row.enabled,
        "imported_paused": row.imported_paused, "currency": row.currency,
        "request_phase": row.request_phase, "request_opens_at": row.request_opens_at, "request_closes_at": row.request_closes_at,
        "allowed_categories": row.allowed_categories, "exclusions": row.exclusions, "claim_due_at": row.claim_due_at,
        "attendance_required": row.attendance_required, "require_project_submission": row.require_project_submission,
        "min_distance_km": str(row.min_distance_km) if row.min_distance_km is not None else None,
        "min_application_stage": row.min_application_stage,
        "award_accept_days": row.award_accept_days, "category_limits": row.category_limits,
        "finance_policy_revision": row.finance_policy_revision}
    if finance:
        value.update(award_mode=row.award_mode, tier_rules=row.tier_rules, eligible_countries=row.eligible_countries,
            eligible_cohorts=row.eligible_cohorts, permitted_venue_sources=row.permitted_venue_sources,
            pools=[pool_detail(pool) for pool in row.pools.order_by("pk")])
    return value


def request_detail(row, *, sensitive=False, screening=False):
    value = {"id": row.pk, "uuid": str(row.uuid), "version": row.version, "state": row.state, "kind": row.kind,
        "member_id": row.member_id, "currency": row.currency, "estimated_total_minor": row.estimated_total_minor,
        "category_estimates": row.category_estimates, "submitted_at": row.submitted_at, "reason_code": row.reason_code}
    if sensitive:
        value.update(itinerary=json.loads(row.itinerary), need_statement=row.need_statement,
            distance_km=str(row.distance_km) if row.distance_km is not None else None, reason=row.reason)
    if screening:
        from .pools import read_pool
        award_row = GrantAward.objects.filter(request=row).select_related("pool").first()
        pool = award_row.pool if award_row else read_pool(row.programme, row.kind)  # G14
        award = GrantAward.objects.filter(request=row).first()
        value.update(budget={"pool_id": pool.pk, "pool_version": pool.version,
            "available_minor": pool.total_minor - pool.reserved_minor - pool.committed_minor},
            award=award_detail(award) if award else None)
    return value


def award_detail(row):
    return {"id": row.pk, "uuid": str(row.uuid), "version": row.version, "state": row.state,
        "amount_minor": row.amount_minor, "currency": row.currency, "accept_by": row.accept_by,
        "due_revision": row.due_revision, "award_revision": row.revisions.order_by("-revision").first().revision,
        "rule_revision": row.rule_revision, "calculation_snapshot": row.calculation_snapshot,
        "accepted_at": row.accepted_at, "reason_code": row.reason_code}


def claim_detail(row, *, owner=False, finance=False, detail=True):
    obligation = EventPayoutObligation.objects.filter(source_kind="event_reimbursement", source_uuid=row.uuid,
        makerspace_id=row.event.makerspace_id).first()
    payout = payout_summary(obligation) if obligation else None
    display_state = "paid" if payout and payout["remaining_minor"] == 0 and payout["approved_minor"] > 0 else row.state
    actions = []
    due = row.info_due_at if row.state == "returned_for_info" else row.effective_due_at
    from .attendance import participating
    if (owner and row.state in ("draft", "open", "returned_for_info") and due > timezone.now()
            and row.event.ends_at <= timezone.now() and row.event.status != "cancelled" and participating(row.award.request)):
        actions += ["edit", "submit"]
    if (owner and row.state in ("rejected", "partially_approved") and not row.appeal_used and row.appeal_due_at
            and row.appeal_due_at > timezone.now() and (payout is None or payout["effective_paid_minor"] == 0)):
        actions.append("appeal")
    if finance:
        if row.state in ("submitted", "under_review"):
            actions += ["decide", "attendance_attest", "receipt_override"]
        if row.state in ("draft", "open", "returned_for_info"):
            actions += ["extend", "attendance_attest", "receipt_override"]
        if row.state in ("approved", "partially_approved", "rejected") and (payout is None or payout["effective_paid_minor"] == 0):
            actions.append("correct_decision")
    elif not owner and row.state in ("submitted", "under_review"):
        actions.append("recommend")
    value = {"id": row.pk, "uuid": str(row.uuid), "version": row.version, "state": row.state,
        "display_state": display_state, "member_id": row.member_id, "award_id": row.award_id,
        "current_revision": row.current_revision_id, "current_decision": row.current_decision_id,
        "effective_due_at": row.effective_due_at, "info_due_at": row.info_due_at, "due_revision": row.due_revision,
        "appeal_due_at": row.appeal_due_at, "appeal_used": row.appeal_used,
        "domain_closed_at": row.domain_closed_at, "allowed_actions": actions, "payout": payout}
    if detail and (owner or finance):
        value["draft"] = json.loads(row.draft_payload) if owner else None
        value["revisions"] = [{"id": revision.pk, "revision": revision.revision, "submitted_at": revision.submitted_at,
            "currency": revision.currency, "total_minor": revision.total_minor,
            "lines": [line_detail(line) for line in revision.lines.order_by("line_uuid")]} for revision in row.revisions.order_by("revision")]
        value["decisions"] = [{"id": d.pk, "sequence": d.sequence, "outcome": d.outcome,
            "approved_total_minor": d.approved_total_minor, "currency": d.currency, "reason_code": d.reason_code,
            "reason": d.reason, "decided_at": d.decided_at, "lines": [{"line_uuid": str(l.line.line_uuid),
            "approved_minor": l.approved_minor, "reason_code": l.reason_code, "reason": l.reason}
            for l in d.line_decisions.select_related("line").order_by("pk")]} for d in row.decisions.order_by("sequence")]
    elif detail and row.current_revision_id:
        value["receipt_metadata"] = [{"line_uuid": str(line.line_uuid), "category": line.category,
            "converted_minor": line.converted_minor, "receipt_present": True, "sha256": line.receipt_hash}
            for line in row.current_revision.lines.order_by("line_uuid")]
    return value


def line_detail(line):
    return {"line_uuid": str(line.line_uuid), "category": line.category, "vendor": line.vendor,
        "description": line.description, "traveller": line.traveller, "expense_date": line.expense_date,
        "original_amount_minor": line.original_amount_minor, "original_currency": line.original_currency,
        "fx_rate": str(line.fx_rate), "rate_date": line.rate_date, "rate_source": line.rate_source,
        "source_note": line.source_note, "converted_minor": line.converted_minor, "route": json.loads(line.route),
        "lodging_starts_on": line.lodging_starts_on, "lodging_ends_on": line.lodging_ends_on,
        "lodging_nights": line.lodging_nights,
        "receipt": {"asset_id": line.finance_asset_id, "sha256": line.receipt_hash,
            "generation": line.finance_asset.generation, "state": line.finance_asset.state}}


def member_summary(event, actor):
    programme = ReimbursementProgramme.objects.filter(event=event).first()
    row = GrantRequest.objects.filter(event=event, member=actor).first()
    award = GrantAward.objects.filter(request=row).first() if row else None
    claim = ReimbursementClaim.objects.filter(award=award).first() if award else None
    available = programme is not None and programme.enabled and not programme.imported_paused and event.status != "cancelled"
    return {"available": available, "programme": programme_detail(programme),
        "request_context": context(programme) if available else None,
        "request": request_detail(row, sensitive=True) if row else None,
        "award": award_detail(award) if award else None,
        "claim": claim_detail(claim, owner=True) if claim else None,
        "allowed_actions": (["create_request"] if available and row is None else []) +
            (["accept_award", "decline_award"] if available and award and award.state == "offered"
                and timezone.now() < award.accept_by else [])}

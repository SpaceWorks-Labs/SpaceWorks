"""Retention-safe domain purge provider, used for BOTH Events and R purges."""
import json
from collections import Counter
from django.db import connection
from django.db.models import Q
from django.core.exceptions import ValidationError
from apps.payments.event_payouts.obligation_models import EventPayoutObligation
from apps.payments.event_payouts.attachment_models import FinanceAttachment
from .config_models import ReimbursementProgramme
from .award_models import GrantAward
from .claim_models import ReimbursementClaim
from .claim_decision_models import ClaimAppeal


def preflight(makerspace_id):
    claims = ReimbursementClaim.objects.filter(event__makerspace_id=makerspace_id)
    awards = GrantAward.objects.filter(request__event__makerspace_id=makerspace_id)
    obligations = EventPayoutObligation.objects.filter(makerspace_id=makerspace_id, source_kind="event_reimbursement")
    assets = FinanceAttachment.objects.filter(makerspace_id=makerspace_id)
    counts = Counter()
    counts["unfinished_reimbursement_awards"] = awards.filter(Q(state__in=("offered", "accepted")) |
        Q(reservation__held_minor__gt=0) | Q(reservation__state="held") | Q(reservation__isnull=True) |
        (Q(state__in=("forfeited", "expired")) & ~Q(reservation__state="released"))).distinct().count()
    counts["unfinished_reimbursement_claims"] = claims.filter(Q(domain_closed_at__isnull=True) |
        Q(state__in=("draft", "open", "submitted", "returned_for_info", "under_review")) |
        Q(appeal__resolution_at__isnull=True, appeal__isnull=False)).distinct().count()
    counts["missing_core_reimbursement_evidence"] += (claims.filter(current_decision__approved_total_minor__gt=0)
        .exclude(uuid__in=obligations.values("source_uuid")).count())
    for obligation in obligations.order_by("pk").iterator():
        invalid = obligation.current_revision_id is None or not obligation.eligibility_evidence
        for revision in obligation.revisions.order_by("sequence"):
            try:
                from apps.payments.event_payouts.decision_snapshots import validate_summary
                summary = validate_summary(json.loads(revision.decision_summary))
                if summary is None:
                    # Validators may return None after successful validation.
                    summary = json.loads(revision.decision_summary)
                if summary["source"]["claim_uuid"] != str(obligation.source_uuid):
                    raise ValueError("binding")
            except (ImportError, ValueError, TypeError, KeyError):
                invalid = True
                break
        counts["missing_core_reimbursement_evidence"] += bool(invalid)
    for claim in claims.filter(domain_closed_at__isnull=False).order_by("pk").iterator():
        obligation = obligations.filter(source_uuid=claim.uuid).first()
        for asset in assets.filter(binding_uuid=claim.uuid).order_by("pk"):
            if obligation:
                valid = asset.obligation_id == obligation.pk
            else:
                valid = bool(asset.terminal_financial_at and asset.closure_operation_id and asset.closure_reason_code
                    and asset.retention_policy_revision and asset.expires_at and asset.staging_key and asset.object_key)
            if not valid:
                counts["missing_finance_attachment_closure"] += 1
    blockers = [{"code": key, "count": value} for key, value in sorted(counts.items()) if value]
    return {"allowed": not blockers, "blockers": blockers, "preserved_core_obligations": obligations.count(),
            "preserved_finance_attachments": assets.count()}


def delete(makerspace, cursor):
    """G holds source/fences/sorted events/host BEFORE bypassing DELETE guards."""
    if not connection.in_atomic_block:
        raise RuntimeError("Domain purge requires the locked purge transaction")
    result = preflight(makerspace.pk)
    if not result["allowed"]:
        raise ValidationError({"code": "unfinished_reimbursements", "blockers": result["blockers"]})
    claims = ReimbursementClaim.objects.filter(event__makerspace=makerspace)
    from apps.payments.event_payouts.attachment_workflow import close_binding_locked
    from apps.audit.services import record
    for claim in claims.order_by("pk"):
        unbound = FinanceAttachment.objects.filter(makerspace=makerspace, binding_kind="claim",
            binding_uuid=claim.uuid, obligation__isnull=True).order_by("pk")
        first = unbound.first()
        if first:
            # Reassert the persisted anchor, reason and operation. Never start a
            # new retention clock at purge time or discard a held-file locator.
            close_binding_locked(makerspace_id=makerspace.pk, binding_kind="claim", binding_uuid=claim.uuid,
                terminal_at=first.terminal_financial_at, reason_code=first.closure_reason_code,
                operation_id=first.closure_operation_id)
            record(None, "event.reimbursement.module_purge_no_liability", makerspace=makerspace, target=claim,
                meta={"claim_id": claim.pk, "attachment_count": unbound.count(), "reason_code": "module_purge_no_liability"})
    from uuid import NAMESPACE_URL, uuid5
    from apps.payments.event_payouts.purge import detach_locked
    from .config_models import ReimbursementProgramme as Programme
    from .payout_facts import facts_for
    obligations = list(EventPayoutObligation.objects.select_for_update().filter(makerspace=makerspace,
        source_kind="event_reimbursement", source_uuid__in=claims.values("uuid")).order_by("pk"))
    # Capture full canonical facts before the domain rows disappear; core keeps them as
    # retained-only evidence that finance must acknowledge before the next payout.
    facts = {}
    for obligation in obligations:
        claim = claims.select_related("event", "member", "award__request").get(uuid=obligation.source_uuid)
        facts[obligation.pk] = facts_for(claim=claim, programme=Programme.objects.get(event=claim.event),
                                         obligation=obligation)
    detach_locked(obligations, actor=None, facts_by_obligation=facts,
                  operation_id=uuid5(NAMESPACE_URL, f"spaceworks:reimbursement-module-purge:{makerspace.pk}"))
    # No finance object is collected/deleted. Core keeps its original retention
    # anchors and durable all-version cleanup locators after the FK graph goes.
    count, labels = ReimbursementProgramme.objects.filter(event__makerspace=makerspace).delete()
    return count, labels


def delete_domain_for_tenant(makerspace, cursor):
    """Whole-tenant purge uses its existing destructive core graph, not preflight."""
    if not connection.in_atomic_block:
        raise RuntimeError("Tenant purge requires its authorized transaction")
    return ReimbursementProgramme.objects.filter(event__makerspace=makerspace).delete()

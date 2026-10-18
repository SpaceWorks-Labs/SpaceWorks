"""Domain-purge retention hooks. Whole-tenant deletion remains lifecycle.purge."""
import json
from dataclasses import replace
from django.db import connection, transaction
from apps.audit.services import record
from .decision_snapshots import validate_summary
from .errors import require
from .preflight import Facts


def preflight_locked(obligations):
    require(connection.in_atomic_block, "locked_transaction_required")
    for row in obligations:
        require(row.current_revision_id is not None and row.revisions.exists(), "core_decision_evidence_missing")
        for revision in row.revisions.order_by("sequence"):
            summary = validate_summary(json.loads(revision.decision_summary))
            require(summary["source"]["claim_uuid"] == str(row.source_uuid)
                and summary["award"]["currency"] == row.currency, "core_decision_evidence_missing")
            if revision.kind == "decision":
                require(revision.approved_minor == summary["totals"]["approved_minor"], "core_decision_evidence_missing")
        if row.terminal_financial_at is not None:
            require(not row.attachments.filter(terminal_financial_at__isnull=True).exists(), "finance_attachment_closure_missing")


def detach_locked(obligations, *, actor, operation_id, facts_by_obligation):
    """G/R call under event/pool/claim -> SORTED core obligation locks."""
    require(connection.in_atomic_block, "locked_transaction_required")
    rows = tuple(obligations)
    with transaction.atomic():
        preflight_locked(rows)
        for row in rows:
            if row.domain_coordination_state == "detached":
                continue
            facts = facts_by_obligation.get(row.pk)
            require(isinstance(facts, Facts), "core_eligibility_evidence_missing")
            facts = replace(facts, retained_only=True)
            from .eligibility_workflow import publish_locked
            publish_locked(row, evidence_revision=row.eligibility_revision + 1,
                evidence=facts.as_dict(), eligible=facts.eligible, reason_code="module_purge_snapshot", actor=actor,
                require_acknowledgement=True)
            row.domain_coordination_state, row.version = "detached", row.version + 1
            row.save(update_fields=["domain_coordination_state", "version"])
            record(actor, "finance.event_payout.detached", makerspace=row.makerspace, target=row,
                meta={"obligation_id": str(row.pk), "operation_id": str(operation_id)})


def preserve_no_liability_locked(*, attachments, actor=None):
    """Preflight only: domain terminality MUST be established by the owning lane."""
    require(connection.in_atomic_block, "locked_transaction_required")
    for row in attachments:
        require(row.obligation_id is None and row.terminal_financial_at is not None and row.closure_operation_id
            and row.closure_reason_code and row.expires_at is not None, "finance_attachment_closure_missing")
        record(actor, "finance.attachment.closure_preserved", makerspace=row.makerspace, target=row,
               meta={"asset_id": row.pk, "reason_code": "module_purge_no_liability"})


def collect_whole_tenant_locked(makerspace_id):
    from .cleanup import collect_tenant_locked
    require(connection.in_atomic_block, "locked_transaction_required")
    return collect_tenant_locked(makerspace_id)

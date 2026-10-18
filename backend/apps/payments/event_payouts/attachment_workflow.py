"""Core closure owns retention anchors even after claim/event module removal."""
from datetime import timedelta
from django.utils import timezone
from apps.audit.services import record
from .errors import require
from .attachment_models import FinanceAttachment
from .attachment_uploads import create_locked, presign
from .attachment_processing import complete_locked, process


def close_binding_locked(*, makerspace_id, binding_kind=None, binding_uuid=None, obligation=None,
                         terminal_at, reason_code, operation_id, bound_obligation=None):
    require(terminal_at is not None and timezone.is_aware(terminal_at), "invalid_financial_closure")
    rows = FinanceAttachment.objects.select_for_update().filter(makerspace_id=makerspace_id)
    if obligation is not None:
        rows = rows.filter(obligation=obligation)
    else:
        require(binding_kind in ("claim", "payee") and binding_uuid is not None, "invalid_attachment_binding")
        rows = rows.filter(binding_kind=binding_kind, binding_uuid=binding_uuid)
        rows = rows.filter(obligation=bound_obligation) if bound_obligation else rows.filter(obligation__isnull=True)
    for row in rows.order_by("pk"):
        if row.terminal_financial_at is not None:
            if obligation is not None and row.closure_reason_code == "superseded_unused":
                continue
            # An idempotent purge or retry reasserts the original anchor. Never
            # shortens evidence retention or sets the clock to the purge date.
            require((row.terminal_financial_at, row.closure_reason_code) == (terminal_at, reason_code),
                    "financial_closure_conflict")
            continue
        row.terminal_financial_at, row.closure_reason_code = terminal_at, reason_code
        row.closure_operation_id = operation_id
        days = 30 if row.purpose == "reimbursement_payee_document" else row.retention_days_snapshot
        row.expires_at = terminal_at + timedelta(days=days)
        row.version += 1
        row.save()
        record(None, "finance.attachment.closed", makerspace=row.makerspace, target=row,
            meta={"asset_id": row.pk, "reason_code": reason_code, "operation_id": str(operation_id)})


def reopen_locked(obligation):
    for row in obligation.attachments.select_for_update().exclude(
        state__in=("expired", "deleting", "deleted")).order_by("pk"):
        if row.closure_reason_code == "superseded_unused":
            continue
        row.terminal_financial_at = row.expires_at = row.closure_operation_id = None
        row.closure_reason_code = ""
        row.version += 1
        row.save()
        record(None, "finance.attachment.reopened", makerspace=obligation.makerspace, target=row,
               meta={"asset_id": row.pk})


def bind_claim_locked(*, obligation, claim_uuid):
    rows = FinanceAttachment.objects.select_for_update().filter(makerspace_id=obligation.makerspace_id,
        binding_kind="claim", binding_uuid=claim_uuid).order_by("pk")
    for row in rows:
        require(row.obligation_id in (None, obligation.pk), "attachment_obligation_mismatch")
        require(row.owner_member_id == obligation.owner_member_id and row.event_id_snapshot == obligation.event_id_snapshot,
                "attachment_scope_mismatch")
        if row.obligation_id == obligation.pk:
            continue
        row.obligation, row.version = obligation, row.version + 1
        if row.state not in ("expired", "deleting", "deleted"):
            row.terminal_financial_at = row.expires_at = row.closure_operation_id = None
            row.closure_reason_code = ""
        row.save()
        record(None, "finance.attachment.bound", makerspace=obligation.makerspace, target=row,
               meta={"asset_id": row.pk, "obligation_id": str(obligation.pk)})


def attach_locked(row, *, binding_uuid, owner_id):
    require(row.expired_at is None and (row.state == "attached" or row.created_at + timedelta(hours=24) > timezone.now()),
            "asset_expired", status=410)
    require(row.binding_uuid == binding_uuid and row.owner_member_id == owner_id
            and row.state in ("ready", "attached") and row.scan_status in ("clean", "skipped")
            and row.actual_bytes == row.expected_bytes and row.canonical_mime and row.sha256,
            "receipt_unavailable")
    if row.state == "ready":
        row.state, row.attached_at, row.version = "attached", timezone.now(), row.version + 1
        row.save(update_fields=["state", "attached_at", "version"])
        record(None, "finance.attachment.attached", makerspace=row.makerspace, target=row,
               meta={"asset_id": row.pk, "generation": row.generation})


def hold_locked(row, *, actor, reason_code, hold_until, release=False):
    require(row.state not in ("expired", "deleting", "deleted"), "attachment_expired", status=410)
    require(release or hold_until is not None and hold_until > timezone.now(), "hold_review_date_required", status=400)
    row.legal_hold_reason_code = "" if release else reason_code
    row.legal_hold_until = None if release else hold_until
    row.version += 1
    row.save()
    record(actor, "finance.attachment.hold_released" if release else "finance.attachment.held", makerspace=row.makerspace,
           target=row, meta={"asset_id": row.pk, "reason_code": reason_code})
    if release:
        from .tasks import queue_retention
        queue_retention(asset_id=row.pk)


def expire_locked(row, *, obligation, now, abandoned=False):
    from .eligibility_workflow import retention_held
    from .cleanup_models import FinanceObjectCleanup
    if row.state in ("expired", "deleting", "deleted"):
        return False
    if row.legal_hold_reason_code or row.legal_hold_until is not None:
        return False
    if obligation is not None and retention_held(obligation):
        return False
    if abandoned:
        require(row.state in ("initiated", "uploaded", "validating", "ready", "failed")
            and row.attached_at is None and row.created_at + timedelta(hours=24) <= now, "retention_active")
    else:
        require(row.terminal_financial_at and row.expires_at and row.expires_at <= now, "retention_active")
        if obligation is not None:
            from .queries import paid
            # Superseded unused routing documents can expire independently.
            unused = row.binding_kind == "payee" and not obligation.entries.filter(payee_revision_id=row.binding_uuid).exists()
            current = obligation.payee_revisions.filter(pk=row.binding_uuid, state="current").exists()
            require(obligation.state == "cancelled" or paid(obligation) == obligation.approved_minor
                or unused and not current, "attachment_retained_for_unpaid_obligation", status=423)
    row.state, row.expired_at, row.version = "expired", now, row.version + 1
    row.lease_token = row.lease_until = None
    row.save()
    locator = FinanceObjectCleanup.objects.select_for_update().get(asset_id=row.pk)
    locator.next_attempt_at = now
    locator.save(update_fields=["next_attempt_at"])
    record(None, "finance.attachment.expired", makerspace=row.makerspace, target=row,
           meta={"asset_id": row.pk, "abandoned": abandoned})
    return True


def mark_deleted_locked(row, *, now, cleanup_id):
    require(row.state in ("expired", "deleting", "deleted"), "retention_active")
    if row.state == "deleted":
        return
    row.state, row.version = "deleted", row.version + 1
    row.deletion_receipt = {"cleanup_id": str(cleanup_id), "deleted_at": now.isoformat(), "all_versions": True}
    row.save()
    record(None, "finance.attachment.deleted", makerspace=row.makerspace, target=row, meta={"asset_id": row.pk})


def discard_locked(row, *, actor):
    from .cleanup_models import FinanceObjectCleanup
    require(row.attached_at is None and row.state in ("initiated", "uploaded", "validating", "ready", "failed"),
            "attached_finance_evidence_retained")
    require(not row.legal_hold_until and not row.legal_hold_reason_code, "retention_hold_active", status=423)
    if row.obligation_id:
        from .eligibility_workflow import retention_held
        require(not retention_held(row.obligation), "retention_hold_active", status=423)
    row.state, row.expired_at, row.version = "expired", timezone.now(), row.version + 1
    row.lease_token = row.lease_until = None
    row.save()
    locator = FinanceObjectCleanup.objects.select_for_update().get(asset_id=row.pk)
    locator.next_attempt_at = timezone.now()
    locator.save(update_fields=["next_attempt_at"])
    record(actor, "finance.attachment.discarded", makerspace=row.makerspace, target=row, meta={"asset_id": row.pk})

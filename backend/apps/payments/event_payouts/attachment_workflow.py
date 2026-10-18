"""Core closure owns retention anchors even after claim/event module removal."""
from datetime import timedelta
from django.utils import timezone
from apps.audit.services import record
from .errors import require
from .attachment_models import FinanceAttachment


def close_binding_locked(*, makerspace_id, binding_kind=None, binding_uuid=None, obligation=None,
                         terminal_at, reason_code, operation_id):
    require(terminal_at is not None and timezone.is_aware(terminal_at), "invalid_financial_closure")
    rows = FinanceAttachment.objects.select_for_update().filter(makerspace_id=makerspace_id)
    if obligation is not None:
        rows = rows.filter(obligation=obligation)
    else:
        require(binding_kind in ("claim", "payee") and binding_uuid is not None, "invalid_attachment_binding")
        rows = rows.filter(binding_kind=binding_kind, binding_uuid=binding_uuid, obligation__isnull=True)
    for row in rows.order_by("pk"):
        if row.terminal_financial_at is not None:
            # An idempotent purge or retry reasserts the original anchor. Never
            # shortens evidence retention or sets the clock to the purge date.
            require((row.terminal_financial_at, row.closure_reason_code) == (terminal_at, reason_code),
                    "financial_closure_conflict")
            continue
        row.terminal_financial_at, row.closure_reason_code = terminal_at, reason_code
        row.closure_operation_id = operation_id
        row.expires_at = terminal_at + timedelta(days=row.retention_days_snapshot)
        row.version += 1
        row.save()


def reopen_locked(obligation):
    for row in obligation.attachments.select_for_update().exclude(
        state__in=("expired", "deleting", "deleted")).order_by("pk"):
        row.terminal_financial_at = row.expires_at = row.closure_operation_id = None
        row.closure_reason_code = ""
        row.version += 1
        row.save()


def bind_claim_locked(*, obligation, claim_uuid):
    rows = FinanceAttachment.objects.select_for_update().filter(makerspace_id=obligation.makerspace_id,
        binding_kind="claim", binding_uuid=claim_uuid).order_by("pk")
    for row in rows:
        require(row.obligation_id in (None, obligation.pk), "attachment_obligation_mismatch")
        require(row.owner_member_id == obligation.owner_member_id and row.event_id_snapshot == obligation.event_id_snapshot,
                "attachment_scope_mismatch")
        row.obligation, row.version = obligation, row.version + 1
        row.save(update_fields=["obligation", "version"])


def attach_locked(row, *, binding_uuid, owner_id):
    require(row.binding_uuid == binding_uuid and row.owner_member_id == owner_id
            and row.state in ("ready", "attached") and row.scan_status in ("clean", "skipped")
            and row.actual_bytes == row.expected_bytes and row.canonical_mime and row.sha256,
            "receipt_unavailable")
    if row.state == "ready":
        row.state, row.attached_at, row.version = "attached", timezone.now(), row.version + 1
        row.save(update_fields=["state", "attached_at", "version"])

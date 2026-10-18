"""Finance-only file purposes, quota and retention policy; no Events dependency."""
from enum import StrEnum
from django.conf import settings
from django.db.models import Sum
from .attachment_models import FinanceAttachment
from .errors import require
from .retention_policy import RECEIPT_DAYS, PAYEE_DAYS
from .validation import closed


class ReadPurpose(StrEnum):
    FINANCE_REIMBURSEMENT_RECEIPT = "finance_reimbursement_receipt"
    FINANCE_PAYEE_DOCUMENT = "finance_payee_document"


PURPOSES = {"reimbursement_receipt": ReadPurpose.FINANCE_REIMBURSEMENT_RECEIPT,
            "reimbursement_payee_document": ReadPurpose.FINANCE_PAYEE_DOCUMENT}
MIMES = {"application/pdf", "image/jpeg", "image/png"}
MAX_BYTES = 10 * 1024 ** 2


def validate_upload(data, *, purpose):
    closed(data, ("question_id", "filename", "bytes", "mime"))
    require(purpose in PURPOSES, "invalid_file_purpose", status=400)
    cap = getattr(settings, "EVENT_REIMBURSEMENT_FILE_MAX_BYTES", MAX_BYTES)
    require(type(cap) is int and 0 < cap <= MAX_BYTES, "finance_storage_policy_invalid", status=503)
    require(type(data["bytes"]) is int and 0 < data["bytes"] <= cap, "file_too_large", status=413)
    mimes = MIMES | ({"image/heic"} if purpose == "reimbursement_receipt" else set())
    require(data["mime"] in mimes, "file_type_unsupported", status=400)
    name = data["filename"]
    require(isinstance(name, str) and 0 < len(name.strip()) <= 255
        and not any(ord(char) < 32 or ord(char) == 127 for char in name), "invalid_filename", status=400)
    import re
    require(isinstance(data["question_id"], str) and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", data["question_id"]),
            "invalid_question_id", status=400)


def reserve_locked(*, makerspace_id, event_id, owner_id, binding_uuid, question_id, size):
    """Host lock serializes reservations, including simultaneous new uploads."""
    rows = FinanceAttachment.objects.filter(makerspace_id=makerspace_id, event_id_snapshot=event_id).exclude(state="deleted")
    total = rows.aggregate(value=Sum("expected_bytes"))["value"] or 0
    own = rows.filter(owner_member_id=owner_id).aggregate(value=Sum("expected_bytes"))["value"] or 0
    event_limit = getattr(settings, "EVENT_REIMBURSEMENT_EVENT_STORAGE_BYTES", 1024 ** 3)
    member_limit = getattr(settings, "EVENT_REIMBURSEMENT_MEMBER_STORAGE_BYTES", 100 * 1024 ** 2)
    require(type(event_limit) is int and event_limit > 0 and type(member_limit) is int and member_limit > 0,
            "finance_storage_policy_invalid", status=503)
    require(total + size <= event_limit and own + size <= member_limit, "finance_quota_exceeded", status=413)
    count = rows.filter(binding_uuid=binding_uuid, question_id=question_id).exclude(state__in=("expired", "deleting", "failed")).count()
    require(count < 5, "file_count_exceeded", status=413)


def policy_snapshot(makerspace_id, purpose):
    from .cleanup_models import FinanceRetentionPolicy
    row = FinanceRetentionPolicy.objects.filter(makerspace_id=makerspace_id).first()
    configured_days = getattr(settings, "EVENT_REIMBURSEMENT_RECEIPT_RETENTION_DAYS", RECEIPT_DAYS)
    require(type(configured_days) is int and 1 <= configured_days <= 36500, "invalid_retention_policy", status=503)
    require(row is not None or configured_days == RECEIPT_DAYS, "finance_retention_policy_not_initialized", status=503)
    return (row.version if row else 1, (row.receipt_days if row else RECEIPT_DAYS)
            if purpose == "reimbursement_receipt" else PAYEE_DAYS)

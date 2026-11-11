"""The collection sheet: record up to 200 offline payments in one go (parity O-B3, `billing.collection_sheet`).

A treasurer at a chapter meeting collects cash and UPI from many members. Every sheet row is ONE ordinary
offline settlement: `reconcile_payments` writes the `ManualSettlement` receipt, issues the receipt document
and flips the charge in its own transaction -- or, with `billing.maker_checker` on, files a
`SettlementConfirmation` that a SECOND person must confirm. The sheet itself can never confirm anything, so
the two-person rule and the database check behind it hold exactly as for a single payment.

Rows succeed or fail independently: a charge that is already paid, out of scope, or not found fails that row
only, with a typed code, and the rest of the sheet still lands. Only the START of a sheet is limited
(`collection_sheet_rows_monthly`); settling one charge at a time is never blocked.
"""

import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import APIException

from apps.audit import services as audit
from apps.payments.models import Payment

logger = logging.getLogger(__name__)

MAX_ROWS = 200
RECORDED, AWAITING, FAILED = "recorded", "awaiting_confirmation", "failed"


def _failure(exc):
    detail = getattr(exc, "detail", None)
    if isinstance(detail, dict):
        return str(detail.get("code") or getattr(exc, "default_code", "error")), str(detail.get("detail") or "")
    if isinstance(exc, APIException):
        return str(getattr(exc, "default_code", "error")), str(detail or "")
    return "invalid", "; ".join(getattr(exc, "messages", None) or [str(exc)])


def _record_row(actor, space, row):
    from apps.payments.reconciliation import reconcile_payments

    settlement = {"method": row["method"], "reference": row.get("reference", ""),
                  "received_at": row.get("received_at") or timezone.now()}
    with transaction.atomic():
        reconcile_payments(actor=actor, makerspace_id=space.pk, payment_ids=[row["payment_id"]],
                           target_status=Payment.Status.PAID_OFFLINE, settlement=settlement)
        status = Payment.objects.filter(pk=row["payment_id"]).values_list("status", flat=True).first()
    return RECORDED if status == Payment.Status.PAID_OFFLINE else AWAITING


def record_sheet(*, actor, space, rows):
    """Process every row; return `{"summary": {...}, "results": [...]}` (one result per submitted row)."""
    from apps.managed_hosting.extra_quotas import check_extra_quota
    from apps.tenant_migration.gate_runtime import assert_write_allowed

    assert_write_allowed(space.pk)
    check_extra_quota(space, "collection_sheet_rows_monthly", adding=len(rows))  # typed 409, before any row
    seen, results = set(), []
    for index, row in enumerate(rows):
        result = {"index": index, "payment_id": row["payment_id"], "outcome": FAILED, "code": "", "detail": ""}
        if row["payment_id"] in seen:
            result.update(code="duplicate_in_sheet", detail="This charge appears twice on the sheet.")
        else:
            seen.add(row["payment_id"])
            try:
                result["outcome"] = _record_row(actor, space, row)
            except (APIException, DjangoValidationError, ValueError, IntegrityError) as exc:
                result["code"], result["detail"] = _failure(exc)
            except Exception:  # noqa: BLE001 - one broken row must not lose the rest of the sheet
                logger.exception("collection sheet row failed", extra={"makerspace_id": space.pk})
                result.update(code="error", detail="This row could not be recorded.")
        results.append(result)
    summary = {"rows": len(results), **{key: sum(r["outcome"] == key for r in results)
                                       for key in (RECORDED, AWAITING, FAILED)}}
    audit.record(actor, "payment.collection_sheet_recorded", makerspace=space, target=space, meta={
        "rows": summary["rows"], "recorded": summary[RECORDED], "awaiting_confirmation": summary[AWAITING],
        "failed": summary[FAILED]})
    return {"summary": summary, "results": results}

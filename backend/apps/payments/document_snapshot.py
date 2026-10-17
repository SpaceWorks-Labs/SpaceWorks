"""Immutable presentation inputs; only a bill's status is resolved live."""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apps.makerspaces.platform import member_payment_return_url
from apps.makerspaces.theme_validation import HEX_COLOR

DEFAULT_ACCENT = "#FF7447"


def issuer_snapshot(payment, policy, kind):
    space = payment.makerspace
    accent = (space.theme_config or {}).get("accent_color", "")
    snapshot = {
        "name": policy.legal_name or space.name, "address": policy.address,
        "tax_id": policy.tax_id, "footer": policy.footer,
        "contact_email": (space.branding_config or {}).get("support_email", ""),
        "timezone": space.timezone or "UTC",
        "accent_color": accent if isinstance(accent, str) and HEX_COLOR.fullmatch(accent) else DEFAULT_ACCENT,
    }
    if kind == "bill":
        snapshot.update(due_at=payment.due_at.isoformat() if payment.due_at else "",
                        payment_instructions=policy.payment_instructions,
                        payment_navigation=payment_navigation(payment))
    elif kind == "credit_note":
        receipt = payment.documents.filter(kind="receipt", reverses__isnull=True,
            reversed_by__isnull=True).order_by("-issued_at", "-pk").values_list("number", flat=True).first()
        if receipt:
            snapshot["receipt_number"] = receipt
    return snapshot


def payment_navigation(payment):
    url = member_payment_return_url(payment.via_makerspace or payment.makerspace)
    return url if url.endswith("/archived") else url.rstrip("/") + "/payments"


def local_date(document, value):
    if not value:
        return "-"
    from datetime import datetime
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    try:
        zone = ZoneInfo(document.issuer.get("timezone", "UTC"))
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        zone = ZoneInfo("UTC")
    return value.astimezone(zone).date().isoformat()


def bill_status(document):
    if document.kind != "bill":
        return ""
    # Re-query: callers may hold an ORM instance cached before settlement.
    from .models import Payment, PaymentDocument
    status = getattr(document, "live_payment_status", None)
    if status is None:
        status = Payment.objects.values_list("status", flat=True).get(pk=document.payment_id)
    if status in ("paid_online", "paid_offline"):
        if hasattr(document, "live_receipt_number"):
            number = document.live_receipt_number
        else:
            number = PaymentDocument.objects.filter(payment_id=document.payment_id, kind="receipt",
                reverses__isnull=True, reversed_by__isnull=True).order_by("-issued_at", "-pk").values_list("number", flat=True).first()
        return f"Paid — see receipt {number}" if number else "Paid"
    return {"pending": "Unpaid", "waived": "Waived", "canceled": "Cancelled"}.get(status, "")


def with_live_status(queryset):
    """One list query, including the current receipt; no per-document lookups."""
    from django.db.models import F, OuterRef, Subquery
    from .models import PaymentDocument
    receipts = PaymentDocument.objects.filter(payment_id=OuterRef("payment_id"), kind="receipt",
        reverses__isnull=True, reversed_by__isnull=True).order_by("-issued_at", "-pk")
    return queryset.annotate(live_payment_status=F("payment__status"),
                             live_receipt_number=Subquery(receipts.values("number")[:1]))

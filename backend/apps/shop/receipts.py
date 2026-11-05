"""The shop receipt (`shop.receipts`, Q-S15): the L5 document, itemised for the counter.

The ledger issues the numbered receipt -- or tax invoice when tax is on -- in the space's
financial-year series shared with all other income (L5); the shop never numbers its own.
This builds what the receipt screen prints at 80 mm and A4: the space's name (and GSTIN),
the L5 document number and title, the itemised lines (HSN code and rate with `shop.tax`
on), the totals, how it was paid and the pickup code. The buyer's personal details are
not on it beyond the name the buyer gave.
"""

from apps.makerspaces.platform import feature_enabled

from .orders_core import order_payment


def _document(payment):
    if payment is None:
        return None
    return payment.documents.filter(kind="receipt", reverses__isnull=True, reversed_by__isnull=True).order_by(
        "-issued_at", "-pk").first()


def receipt_payload(order):
    from apps.payments.tax.models_tax import MakerspaceTaxSettings

    space = order.makerspace
    payment = order_payment(order)
    document = _document(payment)
    tax = MakerspaceTaxSettings.objects.filter(makerspace=space).first()
    shop_tax = feature_enabled(space, "shop.tax")
    breakdown = getattr(document, "tax_breakdown", None) or {}
    lines = [{"label": line.label, "sku": line.sku, "quantity": line.quantity, "unit_amount": line.unit_amount,
              "discount_amount": line.discount_amount, "line_total": line.line_total,
              "hsn_code": line.hsn_code if shop_tax else "", "tax_rate_bps": line.tax_rate_bps if shop_tax else None,
              "tax_amount": line.tax_amount if shop_tax else None} for line in order.lines.all()]
    return {
        "order_id": order.pk, "space_name": space.name, "supplier_gstin": getattr(tax, "gstin", "") or "",
        "document_number": getattr(document, "number", "") or "", "document_title": breakdown.get("title") or
        ("Receipt" if document else ""), "issued_at": getattr(document, "issued_at", None) or order.paid_at,
        "buyer_name": order.guest_name if order.is_guest else "", "pickup_code": order.pickup_code,
        "channel": order.channel, "currency": order.currency, "lines": lines, "subtotal": order.subtotal,
        "discount_total": order.discount_total, "tax_total": order.tax_total, "total": order.amount_due,
        "status": order.status, "paid": payment is None or payment.status in ("paid_online", "paid_offline", "waived"),
        "method": getattr(document, "settlement_method", "") or getattr(payment, "provider", "") or "",
        "notes": breakdown.get("notes") or [],
    }


def email_receipt(order, address=""):
    """Email the receipt to the buyer (their account email, or a guest/desk address given)."""
    from .notices import buyer_notice

    if address and not order.buyer_id and not order.guest_email:
        order.guest_email = address[:254]  # scoped PII: saved through the encrypting model, never .update()
        order.save(update_fields=["guest_email"])
    return buyer_notice(order, "shop_order_receipt", marker=f"receipt-{order.pk}-{order.status}")

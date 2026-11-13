"""Tax sections of a document PDF, drawn only from the frozen `tax_breakdown`.

A document without a breakdown never reaches this module, so every release-1 PDF is
rendered by the unchanged code path in `document_pdf.py`.
"""

from apps.payments.tax.gstin import state_label


def tax_title(document):
    return (document.tax_breakdown or {}).get("title") or document.get_kind_display()


def identity_lines(breakdown):
    """(label, value) pairs printed under the issuer and the payer."""
    lines = []
    if breakdown.get("mode") == "gst_india":
        if breakdown.get("supplier_gstin"):
            lines.append(("Supplier GSTIN", breakdown["supplier_gstin"]))
        if breakdown.get("supplier_state"):
            lines.append(("Supplier state", state_label(breakdown["supplier_state"])))
        if breakdown.get("recipient_gstin"):
            lines.append(("Recipient GSTIN", breakdown["recipient_gstin"]))
        if breakdown.get("place_of_supply"):
            lines.append(("Place of supply", state_label(breakdown["place_of_supply"])))
        if breakdown.get("sac_code"):
            lines.append(("SAC", breakdown["sac_code"]))
    return lines


def summary_rows(document):
    """Rows for the tax table: taxable value, each component, total."""
    breakdown = document.tax_breakdown
    figures = breakdown["figures"]
    currency = document.currency.upper()
    rows = [("Taxable value", f"{currency} {figures['taxable']}")]
    for component in figures.get("components", []):
        rate = int(component["rate_bps"]) / 100
        rows.append((f"{component['label']} @ {rate:g}%", f"{currency} {component['amount']}"))
    rows.append(("Total tax", f"{currency} {figures['tax']}"))
    return rows


def footer_notes(document):
    breakdown = document.tax_breakdown
    notes = list(breakdown.get("notes") or [])
    basis = "Prices include tax." if breakdown.get("inclusive", True) else "Tax added to the listed price."
    return [basis, *notes]


def method_text(document):
    """'stripe' plus the provider's label when one was captured ("Visa ••4242")."""
    method = document.settlement_method
    if method not in ("stripe", "razorpay"):
        return method
    from apps.payments.models import Payment
    label = Payment.objects.filter(pk=document.payment_id).values_list("method_label", flat=True).first()
    return f"{method} ({label})" if label else method

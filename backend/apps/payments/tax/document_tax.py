"""What a document says about tax, decided once at issue and stored on the row.

`plan_for` returns None on every release-1 path: a bill, or a space with no live tax
policy issuing a document for a charge raised without one. Those documents keep the
release-1 series and a NULL `tax_breakdown`, byte for byte. Otherwise the document gets
an FY number and a frozen breakdown taken from the charge's own `tax_snapshot`.
"""

from dataclasses import dataclass
from decimal import Decimal

from apps.payments.tax.apportion import credit_note_split, figures_json
from apps.payments.tax.engine import split_snapshot

COMPOSITION_NOTE = "Composition taxable person, not eligible to collect tax on supplies."
EXPORT_NOTE = "Supply meant for export under LUT {lut} without payment of integrated tax."
NO_GST_NOTE = "Supply outside the scope of GST; no tax charged."
EXEMPT_NOTE = "Exempt supply; no tax charged."


@dataclass(frozen=True)
class TaxPlan:
    policy: object
    breakdown: dict | None


def _policy(space):
    from apps.payments.tax.models_tax import MakerspaceTaxSettings
    from apps.payments.tax.snapshot import live_settings

    live = live_settings(space)
    return live, live or MakerspaceTaxSettings.objects.filter(makerspace=space).first()


def plan_for(payment, *, kind, amount, refund=None, reverses=None):
    if kind == "bill":
        return None
    live, policy = _policy(payment.makerspace)
    if policy is None or (live is None and not payment.tax_snapshot):
        return None
    if reverses is not None:
        return TaxPlan(policy, reverses.tax_breakdown)
    snapshot = payment.tax_snapshot
    if not snapshot:
        return TaxPlan(policy, None)
    if kind == "credit_note":
        invoice = _current_invoice(payment)
        if invoice is None or not invoice.tax_breakdown:
            return TaxPlan(policy, None)
        earlier = [doc.tax_breakdown["figures"] for doc in _credited(payment) if doc.tax_breakdown]
        split = credit_note_split(invoice.tax_breakdown["figures"], earlier, amount, payment.currency)
        return TaxPlan(policy, breakdown(snapshot, split, kind))
    return TaxPlan(policy, breakdown(snapshot, split_snapshot(amount, snapshot, payment.currency), kind))


def _current_invoice(payment):
    return payment.documents.filter(kind="receipt", reverses__isnull=True, reversed_by__isnull=True).order_by(
        "-issued_at", "-pk").first()


def _credited(payment):
    return payment.documents.filter(kind="credit_note", refund__isnull=False, reversed_by__isnull=True).order_by("pk")


def title(snapshot, kind):
    if kind == "credit_note":
        return "Credit note"
    if snapshot["mode"] == "single":
        return "Tax receipt"
    return "Tax invoice" if snapshot["supply_type"] in ("intra", "inter", "export_lut") else "Bill of supply"


def notes(snapshot):
    supply = snapshot.get("supply_type")
    if supply == "composition":
        return [COMPOSITION_NOTE]
    if supply == "export_lut":
        return [EXPORT_NOTE.format(lut=snapshot.get("lut_number", ""))]
    if supply == "no_gst":
        return [NO_GST_NOTE]
    if supply == "exempt":
        return [EXEMPT_NOTE]
    return ["Tax payable on reverse charge: No."] if snapshot["mode"] == "gst_india" else []


def breakdown(snapshot, split, kind):
    keys = ("mode", "supply_type", "rate_bps", "tax_name", "inclusive", "sac_code", "place_of_supply",
            "supplier_gstin", "supplier_state", "recipient_gstin", "recipient_state", "lut_number", "scheme")
    return {"version": 1, "title": title(snapshot, kind), "notes": notes(snapshot),
            **{key: snapshot.get(key, "") for key in keys}, "figures": figures_json(split)}


def taxable_and_tax(document):
    """(taxable, tax) Decimals for a document, or (amount, 0) when it carries no tax."""
    figures = (document.tax_breakdown or {}).get("figures")
    if not figures:
        return Decimal(document.amount), Decimal("0")
    return Decimal(figures["taxable"]), Decimal(figures["tax"])

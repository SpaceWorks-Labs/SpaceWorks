"""Per-product tax classes (Q-S2, `shop.tax`), built from L5's tax engine, never beside it.

With `shop.tax` on and the space's tax policy live (`billing.tax`), every line is split at
its product's own rate (or the space's rate when the product names none), tax-inclusive,
with the place of supply the space's own state (desk and pickup sales). The lines add up
to one frozen `Payment.tax_snapshot` whose `figures` are the exact sum of the lines, so
L5's documents and credit notes apportion it like any other charge. With `shop.tax` off
the charge takes the space's policy as every other domain does (`freeze_for_charge`).
"""

from decimal import Decimal

from apps.makerspaces.platform import feature_enabled


def _policy(space):
    if not feature_enabled(space, "shop.tax"):
        return None
    from apps.payments.tax.snapshot import live_settings
    return live_settings(space)


def _base(policy, currency):
    from apps.payments.tax.snapshot import snapshot_for
    return snapshot_for(policy, currency=currency, recipient_state=policy.state_code)


def line_taxes(space, items, quote):
    """[{rate_bps, hsn_code, taxable, tax, gross}] per line, or None when tax classes are off."""
    from apps.payments.tax.engine import TAXED_SUPPLIES, tax_on

    policy = _policy(space)
    if policy is None:
        return None
    base = _base(policy, quote.currency)
    taxed = base.get("supply_type") in TAXED_SUPPLIES
    rows = []
    for (variant, _quantity), line in zip(items, quote.lines):
        product = variant.product
        rate = (product.tax_rate_bps if product.tax_rate_bps is not None else policy.rate_bps) if taxed else 0
        taxable, tax, gross = tax_on(line.net, rate, inclusive=True, currency=quote.currency)
        rows.append({"rate_bps": rate, "hsn_code": product.hsn_code, "taxable": taxable, "tax": tax, "gross": gross})
    return rows


def frozen_tax(space, rows, total, currency):
    """`(amount, snapshot)` for `create_payment(frozen_tax=...)`, or None to use the space's policy."""
    from apps.payments.tax.engine import Component, gst_components, q

    policy = _policy(space)
    if policy is None or rows is None:
        return None
    snapshot = _base(policy, currency)
    components = {}
    for row in rows:
        if row["tax"] <= 0 and not row["rate_bps"]:
            continue
        if snapshot.get("mode") == "gst_india":
            parts = gst_components(row["tax"], row["rate_bps"], supply_type=snapshot.get("supply_type", ""),
                                   place_of_supply=snapshot.get("place_of_supply", ""), currency=currency)
        else:
            parts = (Component("tax", snapshot.get("tax_name") or "Tax", row["rate_bps"], row["tax"]),)
        for part in parts:
            code, label, amount = part.code, part.label, part.amount
            current = components.get(code, (label, Decimal("0")))
            components[code] = (label, current[1] + amount)
    rates = {row["rate_bps"] for row in rows}
    uniform = rates.pop() if len(rates) == 1 else 0
    taxable = sum((row["taxable"] for row in rows), Decimal("0"))
    tax = sum((row["tax"] for row in rows), Decimal("0"))
    half = {"cgst", "sgst", "utgst"}
    snapshot.update({
        "rate_bps": uniform, "inclusive": True, "entered_amount": str(q(total, currency)),
        "figures": {"gross": str(q(total, currency)), "taxable": str(taxable), "tax": str(tax), "components": [
            {"code": code, "label": label, "amount": str(amount),
             "rate_bps": (uniform // 2 if code in half else uniform)} for code, (label, amount) in components.items()]},
        "lines": [{"hsn_code": row["hsn_code"], "rate_bps": row["rate_bps"], "taxable": str(row["taxable"]),
                   "tax": str(row["tax"])} for row in rows],
        "source": "shop_tax_classes",
    })
    return q(total, currency), snapshot

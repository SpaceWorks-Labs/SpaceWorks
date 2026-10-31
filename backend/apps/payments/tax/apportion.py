"""Apportion frozen tax figures onto a different amount, exactly (largest remainder).

A partial refund's credit note carries the same proportion of taxable value and of each
tax component as the invoice it reverses. Apportioning against what is still REMAINING
(the invoice minus earlier credit notes) means the last credit note that empties the
charge lands every component exactly on zero -- nothing is credited twice, nothing is
left over by rounding.
"""

from decimal import Decimal

from apps.payments.tax.engine import Component, Split, largest_remainder, q


def figures_json(split):
    return {"gross": str(split.gross), "taxable": str(split.taxable), "tax": str(split.tax),
            "components": [component.as_json() for component in split.components]}


def _parts(figures):
    return [Decimal(figures["taxable"]), *(Decimal(item["amount"]) for item in figures.get("components", []))]


def apportion_figures(figures, amount, currency):
    """Split `amount` in the proportions of `figures` (taxable, then each component)."""
    amount = q(amount, currency)
    gross = Decimal(figures["gross"])
    components = figures.get("components", [])
    if amount == gross:
        shares = _parts(figures)
    else:
        shares = largest_remainder(amount, _parts(figures), currency)
    taxable, rest = shares[0], shares[1:]
    built = tuple(Component(item["code"], item["label"], int(item["rate_bps"]), value)
                  for item, value in zip(components, rest))
    return Split(taxable, sum(rest, q(0, currency)), amount, built)


def remaining_figures(figures, credited):
    """`figures` minus every earlier credit note's figures (same component order)."""
    remaining = {
        "gross": Decimal(figures["gross"]), "taxable": Decimal(figures["taxable"]),
        "components": [dict(item, amount=Decimal(item["amount"])) for item in figures.get("components", [])],
    }
    for previous in credited:
        remaining["gross"] -= Decimal(previous["gross"])
        remaining["taxable"] -= Decimal(previous["taxable"])
        for item, prior in zip(remaining["components"], previous.get("components", [])):
            item["amount"] -= Decimal(prior["amount"])
    tax = sum((item["amount"] for item in remaining["components"]), Decimal(0))
    return {"gross": str(remaining["gross"]), "taxable": str(remaining["taxable"]), "tax": str(tax),
            "components": [dict(item, amount=str(item["amount"])) for item in remaining["components"]]}


def credit_note_split(invoice_figures, earlier_credits, amount, currency):
    """The credit note's split: apportioned from what the invoice still has uncredited."""
    remaining = remaining_figures(invoice_figures, earlier_credits)
    if Decimal(remaining["gross"]) <= 0:
        return apportion_figures(invoice_figures, amount, currency)
    return apportion_figures(remaining, amount, currency)

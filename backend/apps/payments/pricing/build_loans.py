"""Lending lines: rental, deposit, late fee, and the damage / lost suggestion (A1, A2, A5).

* Rental (per item line): `per_loan + min(per_day x days, cap)` per unit, times the
  quantity. The cap applies per unit of each item line (A1). `days` is the planned days
  to the due date at checkout, or the actual days (ceiling of the time issued) at return,
  per the space's `rental_timing`. Renewals are not charged in v1.
* Deposit: release-1 behaviour, with the amount from the rate card -- `fixed` is one
  amount per loan, `per_product` is each item's deposit (override or its own field) x
  quantity. Never discounted, never waived.
* Late fee: per loan (A2), at the highest late rate among the loan's items, for the days
  past the due date plus the space's grace, capped.
* Damage / lost: staff set the amount; this suggests it -- the item's override, then the
  space default, then (lost only) the item's `unit_cost` x quantity (A5).
"""

import math
from decimal import Decimal

from apps.payments.models_pricing import PriceOverride
from apps.payments.pricing.components import component
from apps.payments.pricing.quotes import line, money

PRODUCT = PriceOverride.TargetType.INVENTORY_PRODUCT


def _target(product):
    return {"type": PRODUCT, "id": product.pk, "label": product.name}


def items_of(request, *, accepted=False):
    """(product, quantity) per loan line: issued, else accepted, else requested.

    `accepted=True` reads the accepted quantity first, as the release-1 deposit did.
    """
    rows = []
    for item in request.items.select_related("product"):
        if accepted:
            quantity = item.accepted_quantity or item.issued_quantity
        else:
            quantity = item.issued_quantity or item.accepted_quantity or item.requested_quantity
        if quantity > 0:
            rows.append((item.product, quantity))
    return rows


def rental_lines(card, items, days):
    card.prefetch(PRODUCT, [product.pk for product, _ in items])
    per_loan, per_day = component("loans", "rental_per_loan"), component("loans", "rental_per_day")
    lines = []
    for product, quantity in items:
        targets = ((PRODUCT, product.pk),)
        flat = card.resolve(per_loan.key, targets)
        if flat.amount > 0:
            lines.append(line(per_loan, currency=card.currency, quantity=quantity, unit_amount=flat.amount,
                              rate_source=flat.source, target=_target(product), detail={"units": quantity}))
        daily = card.resolve(per_day.key, targets)
        if daily.amount > 0 and days > 0:
            cap = daily.cap * quantity if daily.cap is not None else None
            lines.append(line(per_day, currency=card.currency, quantity=quantity * days, unit_amount=daily.amount,
                              rate_source=daily.source, cap=cap, target=_target(product),
                              detail={"units": quantity, "days": days,
                                      "cap_per_unit": str(daily.cap) if daily.cap is not None else None}))
    return lines


def deposit_lines(card, items):
    from apps.payments.models import MakerspacePaymentSettings

    entry = component("loans", "deposit")
    mode = card.payment_settings.loan_deposit_mode
    if mode == MakerspacePaymentSettings.LoanDepositMode.FIXED:
        rate = card.resolve(entry.key)
        if rate.amount <= 0:
            return []
        return [line(entry, currency=card.currency, quantity=1, unit_amount=rate.amount, rate_source=rate.source,
                     detail={"basis": "per_loan"})]
    if mode != MakerspacePaymentSettings.LoanDepositMode.PER_PRODUCT:
        return []
    card.prefetch(PRODUCT, [product.pk for product, _ in items])
    lines = []
    for product, quantity in items:
        rate = card.resolve(entry.key, ((PRODUCT, product.pk),), legacy_item=product.deposit_amount)
        if rate.amount > 0:
            lines.append(line(entry, currency=card.currency, quantity=quantity, unit_amount=rate.amount,
                              rate_source=rate.source, target=_target(product), detail={"basis": "per_item"}))
    return lines


def late_lines(card, items, *, due_at, now):
    entry = component("loans", "late_per_day")
    if due_at is None or now is None:
        return []
    card.prefetch(PRODUCT, [product.pk for product, _ in items])
    default = card.default(entry.key)
    winner, winner_product = default, None
    for product, _ in items:
        rate = card.resolve(entry.key, ((PRODUCT, product.pk),))
        if rate.amount > winner.amount:
            winner, winner_product = rate, product
    if winner.amount <= 0:
        return []
    deadline = due_at.timestamp() + default.grace * 86400
    if now.timestamp() <= deadline:
        return []
    days_late = math.ceil((now.timestamp() - deadline) / 86400)
    return [line(entry, currency=card.currency, quantity=days_late, unit_amount=winner.amount,
                 rate_source=winner.source, cap=winner.cap,
                 target=_target(winner_product) if winner_product else None,
                 detail={"days_late": days_late, "grace_days": default.grace})]


def accountability_suggestion(card, product, quantity, issue_type):
    """`(amount, source)` staff are offered for a damaged or missing item (A5)."""
    key = "lost" if issue_type == "missing" else "damage"
    rate = card.resolve(key, ((PRODUCT, product.pk),)) if product is not None else card.default(key)
    if rate.amount > 0 or rate.source in ("override_free", "free_default"):
        return money(rate.amount * quantity, card.currency), rate.source
    if key == "lost" and product is not None and product.unit_cost:
        return money(Decimal(product.unit_cost) * quantity, card.currency), "unit_cost"
    return money(0, card.currency), "none"


def days_between(start, end):
    """Whole days, rounded up; a loan issued and returned within a day is one day."""
    if start is None or end is None or end <= start:
        return 1 if start is not None and end is not None else 0
    return max(1, math.ceil((end - start).total_seconds() / 86400))

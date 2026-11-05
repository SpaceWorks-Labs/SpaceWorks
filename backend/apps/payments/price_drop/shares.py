"""What one item stands at, and what is owed back when its price drops (lane L24).

An item's BASELINE is its frozen price (the quote it was paid at), lowered by every
earlier L24 offer on it: each offer records the price it brought the item down to
(`after`) inside the refund case's `policy_snapshot.shares`, so a second drop offers only
the further difference and a repeated save offers nothing. A case staff declined still
counts -- a declined difference is never offered again.

Every figure is rounded DOWN to the currency and capped at the charge's refundable
balance; `add_due_share` caps it once more under the Payment lock.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from apps.payments.models import Payment
from apps.payments.price_drop import SOURCES
from apps.payments.refund_policy import refundable_balance, round_down

ZERO = Decimal("0")
SETTLED = (Payment.Status.PAID_ONLINE, Payment.Status.PAID_OFFLINE)


@dataclass
class Affected:
    area: str
    item_type: str
    item_id: int
    label: str
    payment: Payment
    #: The item's price before this change and after it, in the quote's own terms.
    before: Decimal
    after: Decimal
    #: Owed back on the charge: rounded down and capped at the refundable balance.
    difference: Decimal
    starts_at: datetime | None = None
    facts: dict = field(default_factory=dict)

    @property
    def item(self):
        return f"{self.item_type}:{self.item_id}"

    def as_json(self, case_id=None):
        return {"area": self.area, "item_type": self.item_type, "item_id": self.item_id, "label": self.label,
                "starts_at": self.starts_at.isoformat() if self.starts_at else None,
                "payment_id": self.payment.pk, "currency": self.payment.currency,
                "paid": str(self.payment.amount), "before": str(self.before), "after": str(self.after),
                "difference": str(self.difference), "case_id": case_id}


def settled_payments(makerspace, subject_type, subject_ids):
    """`{subject_id: Payment}` for the settled charges among `subject_ids`."""
    rows = Payment.objects.filter(makerspace=makerspace, subject_type=subject_type, subject_id__in=list(subject_ids),
                                  status__in=SETTLED).prefetch_related("refund_cases")
    return {row.subject_id: row for row in rows}


def frozen_total(payment, snapshot=None):
    """The quote total a charge was raised from; the charge amount for a pre-L15 charge."""
    total = (snapshot if snapshot is not None else payment.pricing_snapshot or {}).get("total")
    return Decimal(str(total)) if total not in (None, "") else payment.amount


def prior_shares(payment, item):
    found = []
    for case in payment.refund_cases.all():
        for share in (case.policy_snapshot or {}).get("shares", []):
            if share.get("item") == item and share.get("source") in SOURCES:
                found.append(share)
    return found


def standing(before, shares):
    """`(baseline, offered)`: the lowest price the item was brought to, and money offered back."""
    prices = [Decimal(before)] + [Decimal(str(share["after"])) for share in shares if share.get("after") not in (None, "")]
    offered = sum((Decimal(str(share.get("share") or 0)) for share in shares), ZERO)
    return min(prices), offered


def capped(payment, amount):
    return round_down(max(min(Decimal(amount), refundable_balance(payment)), ZERO), payment.currency)


def by_total(payment, item, *, before, after, ratio=None):
    """A whole quote re-priced (bookings, jobs, memberships): `(baseline, owed)` or None.

    `ratio` maps quote money onto the charge (the charge may carry tax on top); by default
    the charge amount over the frozen total.
    """
    baseline, _ = standing(before, prior_shares(payment, item))
    after = Decimal(after)
    if after >= baseline:
        return None
    if ratio is None:
        ratio = payment.amount / Decimal(before) if Decimal(before) > 0 else Decimal(1)
    owed = capped(payment, (baseline - after) * ratio)
    return (baseline, owed) if owed > 0 else None


def by_unit(payment, item, *, before, after, paid):
    """One seat on a shared charge (tickets): `(baseline, owed)` or None.

    `paid` is what the seat cost after its discounts, net of earlier offers; the drop is
    taken in proportion, so a seat bought with a promo gets the promo's share of the drop.
    """
    baseline, _ = standing(before, prior_shares(payment, item))
    after, paid = Decimal(after), Decimal(paid)
    if after >= baseline or baseline <= 0 or paid <= 0:
        return None
    owed = capped(payment, paid * (baseline - after) / baseline)
    return (baseline, owed) if owed > 0 else None

"""The frozen quote: lines, discount, waiver, totals and a digest (lane L15, A6-A8).

Every amount is a `Decimal` rounded HALF-UP per line to the ledger precision (the
currency's exponent, at most two places), and the total is the exact sum of the lines
(A7). A quote is NET of tax: L5 freezes tax on top when the charge is raised (A6).

`digest` names the price a member was shown. A submit that carries it is refused with
409 `price_changed` when the price moved in between, and the new quote is returned (A8):
never charge more than was shown.
"""

import hashlib
import json
from dataclasses import dataclass, field, replace
from decimal import Decimal

from apps.payments.tax.engine import q

SNAPSHOT_VERSION = 1
ZERO = Decimal("0")


@dataclass(frozen=True)
class QuoteLine:
    component: str
    label: str
    subject_type: str | None
    quantity: Decimal
    unit_amount: Decimal
    #: After the cap, before any discount.
    gross: Decimal
    source: str
    discount: Decimal = ZERO
    cap_applied: bool = False
    target: dict | None = None
    detail: dict = field(default_factory=dict)

    @property
    def net(self):
        return self.gross - self.discount

    def as_json(self):
        return {"component": self.component, "label": self.label, "subject_type": self.subject_type,
                "quantity": str(self.quantity), "unit_amount": str(self.unit_amount), "gross": str(self.gross),
                "discount": str(self.discount), "net": str(self.net), "source": self.source,
                "cap_applied": self.cap_applied, "target": self.target, "detail": self.detail}


@dataclass(frozen=True)
class Quote:
    domain: str
    currency: str
    lines: tuple = ()
    #: The one automatic discount applied (A3): {id, name, audience, saving}.
    discount: dict | None = None
    #: An event promo code applied on top: {id, code, saving}.
    promo: dict | None = None
    #: The loan waiver that made components free (A14): {id, components}.
    waiver: dict | None = None
    mode: str = "free"
    notes: tuple = ()
    #: Decision 221(d): plan hours applied before pricing, with the remaining balance
    #: (None unless the member's term included hours); see `bookings.included_hours`.
    included_hours: dict | None = None

    @property
    def subtotal(self):
        return sum((line.gross for line in self.lines), ZERO)

    @property
    def discount_total(self):
        return sum((line.discount for line in self.lines), ZERO)

    @property
    def total(self):
        return sum((line.net for line in self.lines), ZERO)

    @property
    def is_free(self):
        return self.total <= 0

    def subset(self, *subject_types):
        """The lines one `Payment` is raised for (a loan quote spans rental and deposit)."""
        lines = tuple(line for line in self.lines if line.subject_type in subject_types)
        saving = sum((line.discount for line in lines), ZERO)
        discount = {**self.discount, "saving": str(saving)} if self.discount and saving > 0 else None
        return replace(self, lines=lines, discount=discount)

    @property
    def digest(self):
        body = {"domain": self.domain, "currency": self.currency, "total": str(self.total),
                "lines": [[line.component, str(line.quantity), str(line.unit_amount), str(line.net),
                           (line.target or {}).get("id")] for line in self.lines],
                "discount": (self.discount or {}).get("id"), "promo": (self.promo or {}).get("id"),
                "waiver": (self.waiver or {}).get("id")}
        if self.included_hours:
            body["included_minutes"] = self.included_hours.get("applied_minutes", 0)
        encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    def as_json(self):
        return {"version": SNAPSHOT_VERSION, "domain": self.domain, "currency": self.currency, "mode": self.mode,
                "lines": [line.as_json() for line in self.lines], "subtotal": str(self.subtotal),
                "discount_total": str(self.discount_total), "total": str(self.total),
                "discount": self.discount, "promo": self.promo, "waiver": self.waiver,
                "notes": list(self.notes), "digest": self.digest,
                **({"included_hours": self.included_hours} if self.included_hours else {})}

    def to_snapshot(self, **extra):
        """What `Payment.pricing_snapshot` freezes. Insert-only on the charge."""
        return {**self.as_json(), **extra}


def money(value, currency):
    return q(value or 0, currency)


def line(component, *, currency, quantity, unit_amount, rate_source, cap=None, target=None, detail=None):
    """Build one capped, rounded line. The cap (A7) comes before any discount."""
    quantity = Decimal(quantity)
    raw = Decimal(unit_amount) * quantity
    capped = raw
    if cap is not None and cap >= 0 and raw > cap:
        capped = Decimal(cap)
    return QuoteLine(
        component=component.key, label=component.label, subject_type=component.subject_type,
        quantity=quantity, unit_amount=money(unit_amount, currency), gross=money(capped, currency),
        source=rate_source, cap_applied=capped != raw, target=target, detail=detail or {},
    )


@dataclass(frozen=True)
class FrozenQuote:
    """A quote read back from a stored snapshot (#159): charged as frozen, never re-priced."""

    snapshot: dict

    @property
    def total(self):
        return Decimal(self.snapshot.get("total") or "0")

    @property
    def subtotal(self):
        return Decimal(self.snapshot.get("subtotal") or "0")

    @property
    def currency(self):
        return self.snapshot.get("currency", "")

    @property
    def domain(self):
        return self.snapshot.get("domain", "")

    @property
    def lines(self):
        return tuple(self.snapshot.get("lines") or ())

    @property
    def notes(self):
        return tuple(self.snapshot.get("notes") or ())

    @property
    def waiver(self):
        return self.snapshot.get("waiver")

    @property
    def discount(self):
        return self.snapshot.get("discount")

    @property
    def digest(self):
        return self.snapshot.get("digest", "")

    def to_snapshot(self, **extra):
        return {**self.snapshot, **extra}

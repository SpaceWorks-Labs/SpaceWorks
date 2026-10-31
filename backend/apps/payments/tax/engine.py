"""Tax arithmetic. Pure functions over Decimals; no database access except `estimate`.

Every amount is quantized to the ledger's precision: the currency's ISO exponent, capped
at the two decimal places `Payment.amount` stores (a BHD fils cannot be stored, a yen has
no subunit). A component split never invents or loses a unit: the total tax is computed
once and divided between CGST and SGST (or any component set) by largest remainder, so
taxable + every component always equals the gross exactly.
"""

from dataclasses import dataclass, field
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

from apps.payments.money import minor_unit_exponent

BPS = Decimal(10000)


def quantum(currency):
    return Decimal(1).scaleb(-min(minor_unit_exponent(currency), 2))


def q(value, currency):
    return Decimal(value).quantize(quantum(currency), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Component:
    code: str
    label: str
    rate_bps: int
    amount: Decimal

    def as_json(self):
        return {"code": self.code, "label": self.label, "rate_bps": self.rate_bps, "amount": str(self.amount)}


@dataclass(frozen=True)
class Split:
    taxable: Decimal
    tax: Decimal
    gross: Decimal
    components: tuple = field(default_factory=tuple)


def tax_on(amount, rate_bps, *, inclusive, currency):
    """(taxable, tax, gross) for one amount at one rate."""
    amount = q(amount, currency)
    rate = Decimal(int(rate_bps))
    if rate <= 0:
        return amount, q(0, currency), amount
    if inclusive:
        tax = q(amount * rate / (BPS + rate), currency)
        return amount - tax, tax, amount
    tax = q(amount * rate / BPS, currency)
    return amount, tax, amount + tax


def largest_remainder(total, weights, currency):
    """Divide `total` across `weights` exactly, in ledger quanta, by largest remainder."""
    unit = quantum(currency)
    units = int((q(total, currency) / unit).to_integral_value())
    weight_sum = sum(Decimal(weight) for weight in weights)
    if weight_sum <= 0:
        return [q(0, currency) for _ in weights]
    raw = [Decimal(units) * Decimal(weight) / weight_sum for weight in weights]
    floors = [int(value.to_integral_value(rounding=ROUND_DOWN)) for value in raw]
    leftover = units - sum(floors)
    order = sorted(range(len(weights)), key=lambda index: (-(raw[index] - floors[index]), index))
    for index in order[:leftover]:
        floors[index] += 1
    return [Decimal(count) * unit for count in floors]


def gst_components(tax, rate_bps, *, supply_type, place_of_supply, currency):
    """CGST+SGST (or UTGST) for an intra-state supply, IGST otherwise."""
    from apps.payments.tax.gstin import UTGST_STATES

    if supply_type == "intra":
        half = int(rate_bps) // 2
        cgst, local = largest_remainder(tax, [half, int(rate_bps) - half], currency)
        local_code = "utgst" if place_of_supply in UTGST_STATES else "sgst"
        return (Component("cgst", "CGST", half, cgst),
                Component(local_code, local_code.upper(), int(rate_bps) - half, local))
    return (Component("igst", "IGST", int(rate_bps), q(tax, currency)),)


TAXED_SUPPLIES = ("intra", "inter", "single")


def compute(amount, snapshot, currency, *, entered=False):
    """Split one amount under a snapshot's rules.

    `entered=True` reads the amount as the price the space typed, so an exclusive policy
    adds tax on top of it; otherwise the amount is the gross already collected.
    """
    supply = snapshot.get("supply_type", "")
    rate = int(snapshot.get("rate_bps", 0)) if supply in TAXED_SUPPLIES else 0
    inclusive = not entered or snapshot.get("inclusive", True)
    taxable, tax, gross = tax_on(amount, rate, inclusive=inclusive, currency=currency)
    if snapshot.get("mode") == "gst_india":
        if rate:
            components = gst_components(tax, rate, supply_type=supply,
                                        place_of_supply=snapshot.get("place_of_supply", ""), currency=currency)
        else:
            components = (Component("igst", "IGST", 0, q(0, currency)),) if supply == "export_lut" else ()
    else:
        components = (Component("tax", snapshot.get("tax_name") or "Tax", rate, tax),) if rate else ()
    return Split(taxable, tax, gross, components)


def split_snapshot(amount, snapshot, currency):
    """Split a gross ledger amount under a frozen `Payment.tax_snapshot`.

    The snapshot carries the charge's own frozen figures; any other amount (a partial
    credit note, a capture that differed) is apportioned from them, so a full receipt
    always repeats the figures frozen when the charge was raised.
    """
    from apps.payments.tax.apportion import apportion_figures

    figures = snapshot.get("figures")
    if figures:
        return apportion_figures(figures, amount, currency)
    return compute(amount, snapshot, currency)


@dataclass(frozen=True)
class TaxEstimate:
    """What a price becomes under the space's live tax policy. Used by previews and L15."""

    net: Decimal
    tax: Decimal
    gross: Decimal
    inclusive: bool
    mode: str
    components: tuple = ()


def estimate(makerspace, amount, currency, *, member=None, on=None):
    """Gross a price entered under the space's live tax policy. No policy -> gross = amount."""
    from apps.payments.tax.snapshot import build_snapshot

    currency = (currency or "").lower()
    snapshot = build_snapshot(makerspace, currency=currency, member=member)
    amount = q(amount, currency)
    if snapshot is None:
        return TaxEstimate(amount, q(0, currency), amount, True, "none")
    split = compute(amount, snapshot, currency, entered=True)
    return TaxEstimate(split.taxable, split.tax, split.gross, snapshot["inclusive"], snapshot["mode"],
                       split.components)

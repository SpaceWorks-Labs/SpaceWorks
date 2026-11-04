"""Impact preview: which items would change price if a domain's defaults changed (A13).

Runs before any default is saved. It resolves every priced component on every item of
the domain twice -- under the stored card and under the proposed one (built in memory,
nothing written) -- and returns the items whose effective rate moves. An item with its
own price (custom) or set to Free never moves; an item that inherits does.
"""

from decimal import Decimal

from apps.payments.models_pricing import PriceOverride, PricingDefault, PricingDefaultLine
from apps.payments.pricing.components import components
from apps.payments.pricing.rates import RateCard

LIMIT = 200
T = PriceOverride.TargetType


class ProposedCard(RateCard):
    """The stored card with the proposed mode, lines and lending block laid over it."""

    def __init__(self, makerspace, domain, *, mode=None, lines=(), loan_block=None):
        super().__init__(makerspace, domain)
        self.enabled = True
        row = self.row or PricingDefault(makerspace=makerspace, domain=domain)
        self.row = PricingDefault(makerspace=makerspace, domain=domain, mode=mode or row.mode,
                                  rental_timing=row.rental_timing, failed_job_charge=row.failed_job_charge)
        merged = dict(self.lines)
        for entry in lines:
            base = merged.get(entry["component"])
            values = {field: entry.get(field, getattr(base, field, None)) for field in
                      ("amount", "cap", "grace_units", "billing_increment", "minimum")}
            merged[entry["component"]] = PricingDefaultLine(
                component=entry["component"], amount=Decimal(values["amount"] or 0), cap=values["cap"],
                grace_units=values["grace_units"] or 0, billing_increment=values["billing_increment"] or 0,
                minimum=values["minimum"] or 0)
        self.lines = merged
        if loan_block:
            from apps.payments.pricing.adapters import LOAN_FIELD_MAP
            settings_row = self.payment_settings
            for key, column in LOAN_FIELD_MAP.items():
                if key in loan_block:
                    setattr(settings_row, column, loan_block[key])


def _items(makerspace, domain):
    if domain == "loans":
        from apps.inventory.models import InventoryProduct
        rows = InventoryProduct.objects.filter(makerspace=makerspace, is_archived=False).order_by("name", "pk")
        return [(T.INVENTORY_PRODUCT, row, {"deposit": row.deposit_amount}) for row in rows]
    if domain == "machines":
        from apps.machines.models import Machine
        rows = Machine.objects.filter(makerspace=makerspace, is_active=True).select_related("machine_type")
        return [(T.MACHINE, row, {}) for row in rows.order_by("name", "pk")]
    if domain == "bookings":
        from apps.bookings.models import BookableSpace
        rows = BookableSpace.objects.filter(makerspace=makerspace, is_active=True).order_by("name", "pk")
        return [(T.BOOKABLE_SPACE, row, {"per_booking": row.payment_amount}) for row in rows]
    return []


def _rate(card, domain, key, target_type, item, legacy):
    middle = None
    if domain == "machines" and key in ("time", "material", "per_job"):
        from apps.payments.pricing.build_machines import _type_rates
        middle = _type_rates(card, item.machine_type).get(key)
    return card.resolve(key, ((target_type, item.pk),), legacy_item=legacy.get(key), middle=middle)


def impact(makerspace, domain, *, mode=None, lines=(), loan_block=None):
    current = RateCard(makerspace, domain)
    proposed = ProposedCard(makerspace, domain, mode=mode, lines=lines, loan_block=loan_block)
    keys = [entry.key for entry in components(domain) if entry.targets and not entry.staff_set]
    if domain == "loans" and proposed.payment_settings.loan_deposit_mode != "per_product":
        keys.remove("deposit")  # a fixed deposit is one amount per loan, not an item price
    changes, total = [], 0
    rows = _items(makerspace, domain)
    for target_type, item, legacy in rows:
        current.prefetch(target_type, [item.pk])
        proposed.prefetch(target_type, [item.pk])
        for key in keys:
            before = _rate(current, domain, key, target_type, item, legacy)
            after = _rate(proposed, domain, key, target_type, item, legacy)
            if before.amount == after.amount and before.cap == after.cap:
                continue
            total += 1
            if len(changes) < LIMIT:
                changes.append({"target_type": target_type, "target_id": item.pk,
                                "label": getattr(item, "name", str(item.pk)), "component": key,
                                "before": str(before.amount), "after": str(after.amount),
                                "source": after.source})
    return {"domain": domain, "currency": current.currency, "items_checked": len(rows),
            "changed": total, "changes": changes, "truncated": total > len(changes)}

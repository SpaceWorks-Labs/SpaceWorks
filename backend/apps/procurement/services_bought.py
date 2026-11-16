"""Mark a To-Buy item bought (#94): what was paid, to whom, how, and the receipt.

One transaction records the purchase in the finance ledger (`ledger_api.record_expense`,
idempotent per item, `source_kind="procurement.to_buy"`), marks the item received, and,
when the item came from a consumable, puts the stock back up the only ways stock moves:
`inventory/availability.py` for an item, the consumable ledger for a machine consumable.
Money never moves here: it records that staff already paid.

Who may record it (#94): inventory rows the Space Manager or the Inventory Manager;
machine rows the Machine Manager for that machine type or the Space Manager. That is the
shared finance answer `finance_view(...).may_record(domain, machine_type_id)` plus the
procurement stream authority. No approval threshold.
"""

from django.utils.translation import gettext
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit import services as audit
from apps.procurement import access
from apps.procurement.models import ToBuyItem, Vendor

OPEN = (ToBuyItem.Status.REQUESTED, ToBuyItem.Status.APPROVED, ToBuyItem.Status.ORDERED)
SOURCE_KIND = "procurement.to_buy"


def ledger_scope(item):
    """(domain, machine_type_id) the purchase is recorded under (#100 visibility)."""
    if item.kind == ToBuyItem.Kind.PRINTING:
        return "machines", access.provenance_machine_type_id(item) or item.machine_type_id
    return "inventory", None


def _vendor(item, vendor_id):
    if vendor_id is None:
        return None
    vendor = Vendor.objects.filter(pk=vendor_id, makerspace_id=item.makerspace_id, is_archived=False).first()
    if vendor is None:
        raise ValidationError({"vendor_id": gettext("Choose a vendor of this makerspace.")})
    return vendor


def _restock(actor, item, refill_amount):
    """Credit the origin, if any. Returns (kind, id) of what was credited."""
    if item.source_product_id:
        from apps.procurement.services import MoveMode, move_to_inventory
        product = move_to_inventory(
            actor, item, mode=MoveMode.TOPUP, quantity=item.quantity, is_public=False,
            public_availability_mode="status_only", show_public_count=False,
            public_self_checkout_enabled=False)
        return "product", product.pk
    if item.source_shop_variant_id:
        # Release 2 L22: a shop restock goes back on the shop shelf, exactly once.
        from apps.shop.restock import restock_from_to_buy
        variant = restock_from_to_buy(actor, item)
        return "shop_variant", variant.pk
    if item.source_consumable_id:
        if refill_amount is None:
            raise ValidationError({"refill_amount": gettext("Say how much material arrived for this machine consumable.")})
        from apps.procurement.services_refill import refill_consumable
        row = refill_consumable(actor, item, refill_amount)
        return "consumable", row.pk
    return None, None


@transaction.atomic
def mark_bought(actor, item, *, amount, currency, method, reference="", receipt_id=None, vendor_id=None,
                vendor_name="", refill_amount=None, entry_date=None):
    from apps.payments import ledger_api
    from apps.payments.finance_scope import finance_view

    locked = ToBuyItem.objects.select_for_update().select_related("makerspace").get(pk=item.pk)
    if locked.status not in OPEN:
        raise ValidationError({"status": gettext("Only an open To-Buy item can be marked bought.")})
    if not access.can_manage_kind(actor, locked.makerspace_id, locked.kind):
        raise PermissionDenied()
    domain, machine_type_id = ledger_scope(locked)
    if not finance_view(actor, locked.makerspace_id).may_record(domain, machine_type_id):
        raise PermissionDenied(gettext("You cannot record spending in this area."))
    amount = Decimal(amount)
    if amount <= 0:
        raise ValidationError({"amount": gettext("Enter what was paid.")})
    vendor = _vendor(locked, vendor_id)
    supplier = (vendor.name if vendor else str(vendor_name or "").strip() or locked.vendor_name)[:200]
    entry = ledger_api.record_expense(
        locked.makerspace, domain, machine_type_id, amount, currency, method, reference, receipt_id,
        SOURCE_KIND, locked.pk, actor, category="to_buy", description=f"To-Buy: {locked.name}"[:300],
        entry_date=entry_date, counterparty=supplier[:150])
    now = timezone.now()
    locked.status, locked.received_at, locked.purchaser = ToBuyItem.Status.RECEIVED, now, actor
    locked.ordered_at = locked.ordered_at or now
    locked.vendor, locked.vendor_name = vendor, supplier
    locked.actual_unit_cost = (amount / Decimal(max(locked.quantity, 1))).quantize(Decimal("0.001"))
    locked.save(update_fields=["status", "received_at", "ordered_at", "purchaser", "vendor", "vendor_name",
                               "actual_unit_cost", "updated_at"])
    credited, credited_id = _restock(actor, locked, refill_amount)
    audit.record(actor, "procurement.bought", makerspace=locked.makerspace, target=locked, meta={
        "item_id": locked.pk, "ledger_entry_id": entry.pk, "vendor_id": getattr(vendor, "pk", None),
        "domain": domain, "machine_type_id": machine_type_id,
        "credited_product_id": credited_id if credited == "product" else None,
        "credited_consumable_id": credited_id if credited == "consumable" else None,
        "credited_shop_variant_id": credited_id if credited == "shop_variant" else None,
    })
    return locked

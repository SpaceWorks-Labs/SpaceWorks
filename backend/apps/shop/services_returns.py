"""Returns (`shop.returns`, Q-S7): staff take units back and open the refund case for them.

Within the space's returns window (default 14 days from payment; 0 = no returns), staff
choose per line how many units come back and whether each goes back to stock or is
written off; either way a `ShopStockMovement` is written through the availability module.
The money owed is added to the charge's refund case (`add_due_share`) for staff to approve
or decline in the refund queue: nothing is refunded automatically (#59). An order whose
every unit came back is marked `refunded`.
"""

from datetime import timedelta
from decimal import ROUND_DOWN, Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.audit import services as audit

from .errors import ShopRefused
from .models import ShopOrder, ShopOrderReturn, ShopSettings
from .orders_core import order_payment

RETURNABLE = (ShopOrder.Status.PAID, ShopOrder.Status.READY, ShopOrder.Status.COLLECTED)


def returned_quantity(line):
    return line.returns.aggregate(total=Sum("quantity"))["total"] or 0


def _share(line, quantity):
    each = (Decimal(line.line_total) / Decimal(line.quantity)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    return line.line_total if quantity == line.quantity else each * quantity


@transaction.atomic
def record_return(order, *, actor, rows, reason=""):
    """`rows`: [{line_id, quantity, disposition}]. Returns the new `ShopOrderReturn` rows."""
    from apps.inventory.availability import return_shop_stock, shop_stock_units
    from apps.payments.services_refund_partial import add_due_share

    order = ShopOrder.objects.select_for_update().select_related("makerspace").get(pk=order.pk)
    from .gates import write_allowed
    write_allowed(order.makerspace)
    window = ShopSettings.for_makerspace(order.makerspace).returns_window_days
    if order.status not in RETURNABLE or not order.paid_at:
        raise ShopRefused("return_window_closed", "Only a paid order can take a return.")
    if window <= 0 or timezone.now() > order.paid_at + timedelta(days=window):
        raise ShopRefused("return_window_closed", "The returns window for this order has closed.")
    lines = {line.pk: line for line in order.lines.select_related("variant__product")}
    bundles = bool((order.pricing_snapshot or {}).get("bundles"))
    payment = order_payment(order)
    made, owed, pending = [], Decimal("0"), {}
    for row in rows or ():
        line, quantity = lines.get(int(row.get("line_id", 0))), int(row.get("quantity") or 0)
        disposition = row.get("disposition") or ShopOrderReturn.Disposition.RESTOCK
        if line is None or quantity < 1 or disposition not in ShopOrderReturn.Disposition.values:
            raise ShopRefused("return_exceeds_sold", "Each return names a line of this order, a quantity and "
                                                     "restock or write-off.")
        already = returned_quantity(line) + pending.get(line.pk, 0)
        if already + quantity > line.quantity:
            raise ShopRefused("return_exceeds_sold", f"Only {line.quantity - already} of "
                                                     f"{line.label} can still come back.", line_id=line.pk)
        pending[line.pk] = pending.get(line.pk, 0) + quantity
        return_shop_stock(order, shop_stock_units(line.variant, quantity, bundles=bundles), actor=actor,
                          write_off=disposition == ShopOrderReturn.Disposition.WRITE_OFF,
                          reason=(reason or "Returned")[:200])
        amount = _share(line, quantity)
        owed += amount
        made.append(ShopOrderReturn(makerspace=order.makerspace, order=order, line=line, quantity=quantity,
                                    disposition=disposition, amount=amount, reason=(reason or "")[:200],
                                    created_by=actor))
    if not made:
        raise ShopRefused("return_exceeds_sold", "Choose at least one item to take back.")
    case = None
    if payment is not None and owed > 0:
        case = add_due_share(payment, amount=owed, reason_code="shop_return", actor=actor,
                             snapshot={"shop_order_id": order.pk})
    for row in made:
        row.refund_case = case
        row.save()
    if all(returned_quantity(line) >= line.quantity for line in lines.values()):
        order.status, order.closed_at, order.close_reason = ShopOrder.Status.REFUNDED, timezone.now(), "returned"
        order.save(update_fields=["status", "closed_at", "close_reason"])
    for row in made:
        action = "shop.stock_returned" if row.disposition == "restock" else "shop.stock_written_off"
        audit.record(actor, action, makerspace=order.makerspace, target=order, meta={
            "order_id": order.pk, "line_id": row.line_id, "variant_id": row.line.variant_id, "quantity": row.quantity})
    audit.record(actor, "shop.refund_requested", makerspace=order.makerspace, target=order, meta={
        "order_id": order.pk, "case_id": getattr(case, "pk", None), "amount": str(owed),
        "restocked": sum(r.quantity for r in made if r.disposition == "restock"),
        "written_off": sum(r.quantity for r in made if r.disposition == "write_off")})
    return made

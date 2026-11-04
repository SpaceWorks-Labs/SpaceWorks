"""Writing an order and its ONE charge: the shared core of online orders and desk sales.

`create_order` freezes the basket's quote on the order and writes its lines (the frozen
unit price, discount and net, plus the line's tax split with `shop.tax` on).
`raise_charge` records the sale in the ledger through the record-first seam
`create_payment` (subject `shop_order`, domain `shop`), freezing the same quote on the
`Payment`; a free basket raises no charge and is audited `charge.free_by_pricing`.
"""

import secrets
from decimal import Decimal

from django.db import IntegrityError, transaction

from apps.payments.tax.engine import q

from .models import ShopOrder, ShopOrderLine

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def new_pickup_code():
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))


def _save_with_code(order):
    """A pickup code unique in the space; a collision just draws again (no information leaks)."""
    for _attempt in range(8):
        order.pickup_code = new_pickup_code()
        try:
            with transaction.atomic():
                order.save()
            return order
        except IntegrityError as exc:
            if "shop_order_unique_pickup_code" not in str(exc):
                raise
    raise IntegrityError("Could not draw a free pickup code.")


def create_order(space, basket, *, channel, status, actor, buyer=None, guest_name="", guest_email="",
                 pickup_at=ShopOrder.Pickup.SPACE, pickup_event=None, expires_at=None):
    quote = basket.quote
    tax = sum((row["tax"] for row in basket.tax or ()), Decimal("0"))
    order = ShopOrder(
        makerspace=space, channel=channel, status=status, buyer=buyer, guest_name=(guest_name or "")[:200],
        guest_email=(guest_email or "")[:254], pickup_at=pickup_at, pickup_event=pickup_event,
        currency=quote.currency, subtotal=quote.subtotal, discount_total=quote.discount_total, total=quote.total,
        tax_total=q(tax, quote.currency), amount_due=quote.total, digest=quote.digest,
        pricing_snapshot=quote.to_snapshot(bundles=basket.bundles), created_by=actor, expires_at=expires_at)
    _save_with_code(order)
    rows = basket.tax or [None] * len(basket.items)
    ShopOrderLine.objects.bulk_create([
        ShopOrderLine(order=order, variant=variant, label=basket.labels.get(variant.pk, variant.product.name),
                      sku=variant.sku, quantity=quantity, unit_amount=line.unit_amount,
                      discount_amount=line.discount, line_total=line.net,
                      tax_rate_bps=(row or {}).get("rate_bps"), hsn_code=(row or {}).get("hsn_code", ""),
                      taxable_amount=(row or {}).get("taxable", line.net) if row else line.net,
                      tax_amount=(row or {}).get("tax", 0) if row else 0)
        for (variant, quantity), line, row in zip(basket.items, quote.lines, rows)])
    return order


def subject_label(space):
    return f"Shop order at {space.name}"[:255]


def raise_charge(order, basket, *, actor):
    """The order's Payment (or None when free). Sets `amount_due` and the tax total."""
    from apps.payments.models import Payment
    from apps.payments.pricing.charging import raise_priced
    from apps.payments.services import create_payment

    from .tax_lines import frozen_tax

    space = order.makerspace
    frozen = frozen_tax(space, basket.tax, order.total, order.currency)

    def create(**kwargs):
        return create_payment(**kwargs, frozen_tax=frozen)

    payment = raise_priced(basket.quote, makerspace=space, subject_type=Payment.SubjectType.SHOP_ORDER,
                           subject_id=order.pk, member=order.buyer, created_by=actor, target=order,
                           subject_label=subject_label(space), create=create)
    if payment is not None:
        figures = (payment.tax_snapshot or {}).get("figures") or {}
        order.amount_due = payment.amount
        order.tax_total = Decimal(figures.get("tax") or order.tax_total or 0)
        ShopOrder.objects.filter(pk=order.pk).update(amount_due=order.amount_due, tax_total=order.tax_total)
    return payment


def order_payment(order):
    from apps.payments.models import Payment
    return Payment.objects.filter(makerspace_id=order.makerspace_id, subject_type=Payment.SubjectType.SHOP_ORDER,
                                  subject_id=order.pk).first()

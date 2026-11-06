"""Access codes and promo codes for orders (release 2 L6, G29).

Codes stay credentials: matched by their deployment-keyed digest, never echoed, and every
invalid, expired, revoked, exhausted or foreign code is the same 404
(`access_code_invalid` for access codes, the existing "Promo code not found" for promos).
A use is spent only when the order is placed, under the promo row lock.
"""

from django.utils.translation import gettext
from decimal import ROUND_HALF_UP, Decimal

from django.utils import timezone
from rest_framework.exceptions import NotFound

from .invites import code_digest
from .models import EventPromoCode
from .orders_errors import OrderRefused

CENT = Decimal("0.01")


def _live(event, code, *, lock=False):
    rows = EventPromoCode.objects.filter(event=event, makerspace=event.makerspace,
                                         code_digest=code_digest(code, "promo"))
    promo = (rows.select_for_update() if lock else rows).first()
    if promo is None or promo.revoked_at or promo.uses >= promo.max_uses or (
            promo.expires_at and promo.expires_at <= timezone.now()):
        return None
    return promo


def unlocked_types(event, codes, *, lock=False):
    """`(ticket_type_ids, promos)` for the access codes given; any bad code refuses all."""
    ids, promos = set(), []
    for code in codes or ():
        promo = _live(event, code, lock=lock)
        if promo is None or promo.kind != "access":
            raise OrderRefused("access_code_invalid", "That access code is not valid for this event.")
        ids.add(promo.ticket_type_id)
        promos.append(promo)
    return ids, promos


def discount_promo(event, code, *, lock=False):
    if not code:
        return None
    from .feature_gates import require_feature
    require_feature(event, "events.promo_codes")
    promo = _live(event, code, lock=lock)
    if promo is None or promo.kind != "discount":
        raise NotFound(gettext("Promo code not found."))
    return promo


def _off(promo, amount):
    value = amount * Decimal(promo.percent_off) / 100 if promo.percent_off else promo.amount_off
    return min(amount, value).quantize(CENT, rounding=ROUND_HALF_UP)


def apply_promo(promo, ticket_lines):
    """Per-line promo discounts `{index: amount}` and the uses spent.

    `ticket_lines` holds `(index, ticket, quantity, net)` for fixed-price ticket lines,
    `net` being the line after the member discount (the promo goes on top, A3). Per
    ticket: every eligible ticket is discounted and spends one use; with too few uses
    left only that many are. Per order: one discount on the eligible net, one use.
    """
    if promo is None:
        return {}, 0
    eligible = [row for row in ticket_lines if promo.ticket_type_id in (None, row[1].pk) and row[3] > 0]
    if not eligible:
        return {}, 0
    if promo.applies_per == "order":
        subtotal = sum((row[3] for row in eligible), Decimal("0"))
        total, discounts = _off(promo, subtotal), {}
        left = total
        for position, (index, _ticket, _quantity, net) in enumerate(eligible):
            share = left if position == len(eligible) - 1 else (total * net / subtotal).quantize(CENT)
            discounts[index], left = min(share, net), left - min(share, net)
        return discounts, 1
    remaining, discounts, used = promo.max_uses - promo.uses, {}, 0
    for index, _ticket, quantity, net in eligible:
        count = min(quantity, remaining - used)
        if count <= 0:
            break
        unit = (net / quantity).quantize(CENT)
        discounts[index] = min(net, _off(promo, unit) * count)
        used += count
    return discounts, used


def spend(promo, uses):
    if promo is None or uses <= 0:
        return
    locked = EventPromoCode.objects.select_for_update().get(pk=promo.pk)
    if locked.uses + uses > locked.max_uses or locked.revoked_at:
        raise NotFound(gettext("Promo code not found."))
    locked.uses += uses
    locked.save(update_fields=["uses"])

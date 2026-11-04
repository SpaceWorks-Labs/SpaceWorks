"""Pricing a basket: the shop calls L15's `pricing.quote()` (domain `shop`), never its own engine.

`priced_basket` validates the lines (live, active, public for the online shop), applies the
members-only flag and per-order limits when their switches are on, and quotes the basket
with the buyer's one best automatic discount when `shop.member_prices` is on (Q-S6). The
same function serves the preview and the order, so preview = charge (L15 A8); `tax_lines`
adds the per-product tax split when `shop.tax` is on (Q-S2).
"""

from collections import OrderedDict
from dataclasses import dataclass, field

from apps.makerspaces.platform import feature_enabled

from .errors import ShopRefused
from .models import ShopVariant

MAX_LINES = 50
MAX_QUANTITY = 999


@dataclass
class Basket:
    items: list
    quote: object
    bundles: bool
    member: object = None
    tax: list | None = None
    labels: dict = field(default_factory=dict)

    def stock_pairs(self):
        from apps.inventory.availability import shop_stock_units
        pairs = []
        for variant, quantity in self.items:
            pairs += shop_stock_units(variant, quantity, bundles=self.bundles)
        return pairs


def _merged(raw_lines):
    merged = OrderedDict()
    for row in raw_lines or ():
        try:
            variant_id, quantity = int(row["variant_id"]), int(row["quantity"])
        except (KeyError, TypeError, ValueError):
            raise ShopRefused("variant_invalid", "Each line needs an item and a quantity.") from None
        if quantity < 1 or quantity > MAX_QUANTITY:
            raise ShopRefused("variant_invalid", "Choose a quantity between 1 and 999.")
        merged[variant_id] = merged.get(variant_id, 0) + quantity
    if not merged:
        raise ShopRefused("order_empty", "Add at least one item.")
    if len(merged) > MAX_LINES:
        raise ShopRefused("variant_invalid", "An order holds at most 50 different items.")
    return merged


def resolve_items(space, raw_lines, *, public, lock=False):
    """[(variant, quantity)] for the requested lines, in request order."""
    merged = _merged(raw_lines)
    rows = ShopVariant.objects.select_related("product").filter(
        makerspace=space, pk__in=list(merged), is_active=True, archived_at__isnull=True,
        product__is_active=True, product__archived_at__isnull=True)
    if public:
        rows = rows.filter(product__is_public=True)
    if lock:
        rows = rows.select_for_update(of=("self",)).order_by("pk")
    found = {row.pk: row for row in rows}
    missing = [pk for pk in merged if pk not in found]
    if missing:
        raise ShopRefused("item_unavailable", "Some items are no longer on sale.", variant_ids=missing)
    return [(found[pk], quantity) for pk, quantity in merged.items()]


def member_here(space, person):
    """`person` when they hold an active membership of this space, else None."""
    from apps.payments.pricing.discounts import member_plan_ids

    if person is None or not getattr(person, "is_authenticated", False):
        return None
    return person if member_plan_ids(space, person) is not None else None


def check_rules(space, items, member):
    if feature_enabled(space, "shop.member_prices") and member is None:
        blocked = sorted({variant.product.name for variant, _ in items if variant.product.members_only})
        if blocked:
            raise ShopRefused("member_only", "Only members of this space can buy these items.", items=blocked)
    if feature_enabled(space, "shop.order_limits"):
        per_product = {}
        for variant, quantity in items:
            per_product[variant.product_id] = per_product.get(variant.product_id, 0) + quantity
        for variant, _ in items:
            limit = variant.product.max_per_order
            if limit and per_product[variant.product_id] > limit:
                raise ShopRefused("per_order_limit", f"You can take at most {limit} of {variant.product.name}.",
                                  product_id=variant.product_id, limit=limit)


def priced_basket(space, raw_lines, *, person=None, public=True, lock=False):
    """Validate and quote a basket. `person` is the signed-in buyer (or the member at the desk)."""
    from apps.payments import pricing
    from apps.payments.pricing.build_shop import label_for

    items = resolve_items(space, raw_lines, public=public, lock=lock)
    member = member_here(space, person)
    check_rules(space, items, member)
    discounts = feature_enabled(space, "shop.member_prices")
    quote = pricing.quote(space, "shop", None, member=member if discounts else None, params={"lines": items},
                          discounts=discounts)
    basket = Basket(items=items, quote=quote, bundles=feature_enabled(space, "shop.bundles"), member=member,
                    labels={variant.pk: label_for(variant) for variant, _ in items})
    from .tax_lines import line_taxes
    basket.tax = line_taxes(space, items, quote)
    return basket


def quote_payload(space, basket):
    """The preview a buyer (or the desk) sees: lines, discount, tax and what will be charged."""
    from decimal import Decimal

    from apps.payments.tax.engine import estimate

    quote = basket.quote
    rows = basket.tax or [None] * len(quote.lines)
    if basket.tax is not None:
        tax, due, inclusive = sum((row["tax"] for row in basket.tax), Decimal("0")), quote.total, True
    else:
        guess = estimate(space, quote.total, quote.currency, member=basket.member)
        tax, due, inclusive = guess.tax, guess.gross, guess.inclusive
    return {
        "currency": quote.currency, "subtotal": quote.subtotal, "discount_total": quote.discount_total,
        "total": quote.total, "tax_total": tax, "amount_due": due, "tax_inclusive": inclusive,
        "discount_name": (quote.discount or {}).get("name", "") or "", "digest": quote.digest,
        "lines": [{"variant_id": (line.target or {}).get("id"), "label": line.label if not line.target else
                   line.target.get("label", line.label), "quantity": line.quantity, "unit_amount": line.unit_amount,
                   "discount": line.discount, "net": line.net,
                   "tax_rate_bps": row["rate_bps"] if row else None, "tax": row["tax"] if row else None}
                  for line, row in zip(quote.lines, rows)],
    }

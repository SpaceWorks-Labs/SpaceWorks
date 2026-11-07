"""What the public shop shows (`shop.online`): products, variants, prices and stock LABELS.

Public stock follows the public availability rule (Q-S14): with `shop.public_stock` on a
variant says In stock / Low / Sold out, and an exact count only when its product opts in
(`show_exact_stock`); with it off the page says only "Sold out". Never a storage location,
an internal note, a linked inventory item, a cost or another buyer's anything.
"""

from apps.makerspaces.platform import feature_enabled
from apps.payments.availability import charge_tracking_enabled

from .models import ShopProduct, ShopVariant

LOW_FLOOR = 3


def public_products(space):
    return (ShopProduct.objects.filter(makerspace=space, is_public=True, is_active=True, archived_at__isnull=True)
            .prefetch_related("variants", "components__component").order_by("sort_order", "name", "pk"))


def stock_view(space, product, variant, *, labels, bundles):
    from apps.inventory.availability import shop_sellable
    from .gates import stock_source_enabled

    if not stock_source_enabled(space, variant, bundles=bundles):
        return "sold_out", None, True
    left = shop_sellable(variant, bundles=bundles)
    if left <= 0:
        return "sold_out", None, True
    if not labels:
        return None, None, False
    low = left <= max(variant.reorder_point, LOW_FLOOR)
    return ("low" if low else "in_stock"), (left if product.show_exact_stock else None), False


def _variants(space, product, *, labels, bundles, selling):
    rows = []
    for variant in product.variants.all():
        if not variant.is_active or variant.archived_at is not None:
            continue
        label, count, sold_out = stock_view(space, product, variant, labels=labels, bundles=bundles)
        rows.append({"id": variant.pk, "name": variant.name, "options": variant.options or {},
                     "price": variant.price if selling else None,
                     "sold_out": sold_out, "stock_label": label, "stock_count": count})
    return rows


def product_payload(space, product, *, detail=False):
    from apps.inventory import public_image_storage

    labels = feature_enabled(space, "shop.public_stock")
    bundles = feature_enabled(space, "shop.bundles")
    selling = charge_tracking_enabled(space, "shop")
    variants = _variants(space, product, labels=labels, bundles=bundles, selling=selling)
    prices = [row["price"] for row in variants] if selling else []
    payload = {
        "id": product.pk, "slug": product.slug, "name": product.name, "kind": product.kind,
        "category": product.category, "unit": product.unit,
        "image_url": public_image_storage.public_url(product.image_key) or "",
        "price_from": min(prices) if prices else None, "price_to": max(prices) if prices else None,
        "members_only": product.members_only and feature_enabled(space, "shop.member_prices"),
        "max_per_order": product.max_per_order if feature_enabled(space, "shop.order_limits") else None,
        "sold_out": bool(variants) and all(row["sold_out"] for row in variants),
        "variants": variants,
    }
    if detail:
        payload["description"] = product.description
    return payload


def shop_summary(space):
    """Buyer-facing shop facts: currency, how payment works, policy text, pickup choices."""
    from apps.payments.models import MakerspacePaymentSettings

    from .gates import online_rail
    from .models import ShopSettings

    row = ShopSettings.for_makerspace(space)
    return {
        "name": space.name, "currency": MakerspacePaymentSettings.for_makerspace(space).default_currency,
        "pay_online": charge_tracking_enabled(space, "shop") and online_rail(space),
        "guest_checkout": feature_enabled(space, "shop.guest_checkout"),
        "member_prices": feature_enabled(space, "shop.member_prices"), "policy_text": row.policy_text,
        "pickup_note": row.pickup_note, "returns_days": row.returns_window_days if feature_enabled(
            space, "shop.returns") else 0, "pickup_events": pickup_events(space),
        "hold_minutes": row.online_hold_minutes if feature_enabled(space, "shop.holds") else None,
    }


def pickup_events(space):
    if not feature_enabled(space, "shop.event_pickup"):
        return []
    from django.utils import timezone

    from apps.events.website_visibility import listed_events

    events = listed_events(space).filter(ends_at__gt=timezone.now()).order_by("starts_at")[:10]
    return [{"id": event.pk, "title": event.title, "starts_at": event.starts_at} for event in events]


def page_cards(space, limit=6):
    """The Pages `shop` section: a few public products linking to the shop (nothing when off)."""
    from .gates import is_on

    if not is_on(space, "shop.online"):
        return []
    return [{key: value for key, value in product_payload(space, product).items()
             if key in ("id", "slug", "name", "image_url", "price_from", "sold_out")}
            for product in public_products(space)[:limit]]


def variant_by_id(space, variant_id):
    return ShopVariant.objects.select_related("product").filter(makerspace=space, pk=variant_id).first()

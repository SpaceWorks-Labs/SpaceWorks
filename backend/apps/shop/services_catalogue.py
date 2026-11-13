"""Catalogue writes (`MANAGE_SHOP`): products, variants, kit parts and stock movements.

Products and variants are archived, never deleted (orders keep pointing at what was sold).
A product with no options keeps one default variant. A variant may draw on an inventory
item consumable only with `shop.consumable_link` on (Q-S11) -- never a lendable tool. A
kit's bundle parts need `shop.bundles` (Q-S12). Stock moves only through the availability
module. Every write is audited with a literal action.
"""

from django.utils.translation import gettext
import re

from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.audit import services as audit
from apps.makerspaces.platform import feature_enabled

from .errors import ShopRefused
from .models import ShopKitComponent, ShopProduct, ShopVariant

PRODUCT_FIELDS = ("kind", "name", "description", "category", "is_public", "is_active", "sort_order", "unit",
                  "max_per_order", "members_only", "show_exact_stock", "tax_rate_bps", "hsn_code", "bundle_mode")
VARIANT_FIELDS = ("name", "options", "sku", "price", "reorder_point", "is_active", "sort_order")
HSN = re.compile(r"^\d{4,8}$")


def _slug(space, wanted, name, exclude=None):
    base = slugify(wanted or name)[:70] or "item"
    slug, n = base, 2
    rows = ShopProduct.objects.filter(makerspace=space)
    if exclude is not None:
        rows = rows.exclude(pk=exclude)
    while rows.filter(slug=slug).exists():
        slug, n = f"{base}-{n}", n + 1
    return slug


def _check_product(space, values):
    if values.get("hsn_code") and not HSN.match(values["hsn_code"]):
        raise ShopRefused("variant_invalid", gettext("An HSN code is 4 to 8 digits."))
    if values.get("bundle_mode") and values.get("kind", ShopProduct.Kind.KIT) != ShopProduct.Kind.KIT:
        raise ShopRefused("variant_invalid", gettext("Only a kit can be sold as a bundle of its parts."))


def _linked(space, product_id):
    if product_id in (None, ""):
        return None
    if not feature_enabled(space, "shop.consumable_link"):
        raise ShopRefused("link_invalid", gettext("Selling inventory consumables is switched off."))
    from apps.inventory.models import InventoryProduct, TrackingMode
    item = InventoryProduct.objects.filter(pk=product_id, makerspace=space, is_consumable=True, is_archived=False,
                                           tracking_mode=TrackingMode.QUANTITY).first()
    if item is None:
        raise ShopRefused("link_invalid", gettext("Choose a consumable of this space; lendable tools are never sold."))
    return item


def _check_options(options):
    if not isinstance(options, dict) or len(options) > 3 or any(
            not isinstance(k, str) or not isinstance(v, str) or len(k) > 40 or len(v) > 40 for k, v in options.items()):
        raise ShopRefused("variant_invalid", gettext("Options are up to three short name/value pairs, e.g. size: M."))


def _save_variant(space, product, data, actor, variant=None):
    created = variant is None
    variant = variant or ShopVariant(makerspace=space, product=product)
    for name in VARIANT_FIELDS:
        if name in data:
            setattr(variant, name, data[name])
    _check_options(variant.options or {})
    if "linked_product_id" in data:
        linked = _linked(space, data["linked_product_id"])
        if linked is not None and variant.pk and variant.on_hand:
            raise ShopRefused("link_invalid", gettext("Sell or count out this item's own stock before linking it."))
        variant.linked_product = linked
    if variant.sku and ShopVariant.objects.filter(makerspace=space, sku=variant.sku).exclude(pk=variant.pk).exists():
        raise ShopRefused("variant_invalid", gettext("That SKU is already used in this shop."))
    variant.save()
    if created:
        audit.record(actor, "shop.variant_created", makerspace=space, target=variant,
                     meta={"variant_id": variant.pk, "product_id": product.pk, "price": str(variant.price), "linked": bool(variant.linked_product_id)})
    else:
        audit.record(actor, "shop.variant_updated", makerspace=space, target=variant,
                     meta={"variant_id": variant.pk, "product_id": product.pk, "price": str(variant.price), "linked": bool(variant.linked_product_id)})
    return variant


def _components(space, product, rows, actor):
    if not rows:
        product.components.all().delete()
        return
    if not feature_enabled(space, "shop.bundles"):
        raise ShopRefused("feature_off", gettext("Kit bundles are switched off."), feature="shop.bundles")
    ids = [int(row["variant_id"]) for row in rows]
    parts = {v.pk: v for v in ShopVariant.objects.filter(makerspace=space, pk__in=ids, archived_at__isnull=True)
             .exclude(product=product).exclude(product__bundle_mode=True)}
    if len(parts) != len(set(ids)):
        raise ShopRefused("variant_invalid", gettext("A bundle part must be another item of this shop."))
    product.components.all().delete()
    ShopKitComponent.objects.bulk_create([
        ShopKitComponent(makerspace=space, kit=product, component=parts[int(r["variant_id"])],
                                                           quantity=max(int(r.get("quantity") or 1), 1)) for r in rows])


@transaction.atomic
def save_product(space, data, *, actor, product=None):
    """Create or update a product, its variants (by id) and its bundle parts."""
    from .gates import write_allowed
    write_allowed(space)
    values = {name: data[name] for name in PRODUCT_FIELDS if name in data}
    _check_product(space, {**({"kind": product.kind} if product else {}), **values})
    created = product is None
    if created:
        from apps.managed_hosting.extra_quotas import check_extra_quota
        check_extra_quota(space, "shop_products")  # decision 284: typed 409 shop_products_quota_reached
    product = product or ShopProduct(makerspace=space, created_by=actor)
    for name, value in values.items():
        setattr(product, name, value)
    if created or "slug" in data:
        product.slug = _slug(space, data.get("slug"), product.name, exclude=product.pk)
    product.save()
    variants = data.get("variants")
    if variants is None and created:
        variants = [{"name": "Standard", "price": data.get("price", 0)}]
    existing = {v.pk: v for v in product.variants.all()}
    for row in variants or ():
        _save_variant(space, product, row, actor, existing.get(row.get("id")))
    if "components" in data:
        _components(space, product, data["components"] or [], actor)
    if created:
        audit.record(actor, "shop.product_created", makerspace=space, target=product,
                     meta={"product_id": product.pk, "kind": product.kind, "is_public": product.is_public})
    else:
        audit.record(actor, "shop.product_updated", makerspace=space, target=product,
                     meta={"product_id": product.pk, "kind": product.kind, "is_public": product.is_public})
    return product


@transaction.atomic
def archive_product(product, *, actor):
    now = timezone.now()
    product.archived_at, product.is_active = now, False
    product.save(update_fields=["archived_at", "is_active", "updated_at"])
    product.variants.filter(archived_at__isnull=True).update(archived_at=now, is_active=False)
    audit.record(actor, "shop.product_archived", makerspace=product.makerspace, target=product,
                 meta={"product_id": product.pk})
    return product


@transaction.atomic
def archive_variant(variant, *, actor):
    variant.archived_at, variant.is_active = timezone.now(), False
    variant.save(update_fields=["archived_at", "is_active"])
    audit.record(actor, "shop.variant_archived", makerspace=variant.makerspace, target=variant,
                 meta={"variant_id": variant.pk, "product_id": variant.product_id})
    return variant


def move_stock(variant, *, actor, kind, quantity, reason=""):
    """`restock` (+quantity) or an adjustment (count/damage/internal_use, signed delta)."""
    from apps.inventory.availability import InsufficientStock, adjust_shop_stock, restock_shop

    try:
        if kind == "restock":
            row = restock_shop(variant, int(quantity), actor=actor, reason=reason)
        else:
            row = adjust_shop_stock(variant, int(quantity), kind=kind, actor=actor, reason=reason)
    except InsufficientStock as exc:
        raise ShopRefused("out_of_stock", str(exc) or "Stock cannot go below zero or below what is held.") from None
    if kind == "restock":
        audit.record(actor, "shop.stock_restocked", makerspace=variant.makerspace, target=row,
                     meta={"variant_id": row.pk, "kind": kind, "quantity": int(quantity), "on_hand": row.on_hand})
    else:
        audit.record(actor, "shop.stock_adjusted", makerspace=variant.makerspace, target=row,
                     meta={"variant_id": row.pk, "kind": kind, "quantity": int(quantity), "on_hand": row.on_hand})
    return row

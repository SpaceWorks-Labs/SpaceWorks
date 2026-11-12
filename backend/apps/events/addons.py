"""Ticket add-ons (release 2 L6, G30): staff CRUD and event-local stock.

Stock math is local to the event: `stock - sold`, where sold counts the add-on lines of
paid orders and of pending orders under a live hold. Nothing here reads or writes
hardware inventory (`inventory/availability.py` owns that, and is not used).
"""

from django.utils.translation import gettext
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.audit.services import record

from .feature_gates import require_feature
from .models import EventAddon, EventAddonVariant, EventOrder, EventOrderLine
from .orders_errors import OrderRefused

ADDON_FIELDS = ("name", "description", "kind", "amount", "stock", "per_order_limit", "is_active")


def sold(addon, variant=None):
    live = (Q(order__status=EventOrder.Status.PAID)
            | Q(order__status=EventOrder.Status.PENDING, order__hold__released_at__isnull=True,
                order__hold__expires_at__gt=timezone.now()))
    rows = EventOrderLine.objects.filter(live, addon=addon, kind=EventOrderLine.Kind.ADDON)
    if variant is not None:
        rows = rows.filter(variant=variant)
    return rows.aggregate(total=Sum("quantity"))["total"] or 0


def remaining(addon, variant=None):
    """Units left, or None for unlimited."""
    stock = variant.stock if variant is not None else addon.stock
    if not stock:
        return None
    return max(stock - sold(addon, variant), 0)


def require_available(addon, variant, quantity):
    if not addon.is_active or (variant is not None and (not variant.is_active or variant.addon_id != addon.pk)):
        raise OrderRefused("addon_unavailable", gettext("That add-on is not available."), addon_id=addon.pk)
    if variant is None and addon.variants.filter(is_active=True).exists():
        raise OrderRefused("addon_unavailable", gettext("Choose a size or option for this add-on."), addon_id=addon.pk)
    if addon.per_order_limit and quantity > addon.per_order_limit:
        raise OrderRefused("order_limit", gettext("Too many of this add-on in one order."), addon_id=addon.pk)
    left = remaining(addon, variant)
    if left is not None and quantity > left:
        raise OrderRefused("sold_out", gettext("This add-on has sold out."), addon_id=addon.pk)


def _locked(event):
    from .services import _locked_event
    from apps.makerspaces.guards import require_module_locked
    locked = _locked_event(event.pk)
    locked.makerspace = require_module_locked(locked.makerspace, "events")
    require_feature(locked, "events.addons")
    return locked


@transaction.atomic
def create_addon(event, *, actor, variants=(), **values):
    event = _locked(event)
    addon = EventAddon.objects.create(makerspace=event.makerspace, event=event,
                                      **{key: values[key] for key in ADDON_FIELDS if key in values})
    for item in variants:
        EventAddonVariant.objects.create(addon=addon, label=item["label"], stock=item.get("stock", 0))
    record(actor, "event.addon_created", makerspace=event.makerspace, target=addon,
           meta={"event_id": event.pk, "variants": len(variants)})
    return addon


@transaction.atomic
def update_addon(addon, *, actor, variants=None, **values):
    event = _locked(addon.event)
    row = EventAddon.objects.select_for_update().get(pk=addon.pk, event=event)
    changed = sorted(key for key in ADDON_FIELDS if key in values and values[key] != getattr(row, key))
    if "amount" in changed and EventOrderLine.objects.filter(addon=row).exists():
        from .ticketing_edit import ReferencedConflict
        raise ReferencedConflict(gettext("The price is fixed once orders include this add-on. Add a new add-on instead."),
                                 "addon_referenced")
    for key in changed:
        setattr(row, key, values[key])
    if changed:
        row.save(update_fields=changed)
    if variants is not None:
        _sync_variants(row, variants)
    record(actor, "event.addon_updated", makerspace=event.makerspace, target=row, meta={"fields": changed})
    return row


def _sync_variants(addon, variants):
    keep = set()
    for item in variants:
        variant, _ = EventAddonVariant.objects.get_or_create(addon=addon, label=item["label"])
        variant.stock, variant.is_active = item.get("stock", 0), item.get("is_active", True)
        variant.save(update_fields=["stock", "is_active"])
        keep.add(variant.pk)
    # A variant someone ordered is deactivated, never deleted (order lines PROTECT it).
    for variant in addon.variants.exclude(pk__in=keep):
        if variant.order_lines.exists():
            variant.is_active = False
            variant.save(update_fields=["is_active"])
        else:
            variant.delete()


@transaction.atomic
def delete_addon(addon, *, actor):
    event = _locked(addon.event)
    row = EventAddon.objects.select_for_update().get(pk=addon.pk, event=event)
    if row.order_lines.exists():
        from .ticketing_edit import ReferencedConflict
        raise ReferencedConflict(gettext("Orders include this add-on. Deactivate it instead."), "addon_referenced")
    record(actor, "event.addon_deleted", makerspace=event.makerspace, target=row, meta={"event_id": event.pk})
    row.delete()

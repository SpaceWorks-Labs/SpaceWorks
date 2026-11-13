"""Shop merch offered at an event (#135 Q-S18 follow-up): the Shop's list, the event's page.

Staff with `manage_shop` choose which live variants an upcoming event shows. The event's
public page lists them and links into the normal shop with that event as the pickup
(`shop.event_pickup`), so a purchase is an ordinary Shop order and Shop charge -- never a
line on the registration. Everything here needs the Shop module, `shop.event_pickup` and the
Events module; with any off the list is hidden (404) and kept.
"""

from django.utils.translation import gettext
from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.makerspaces.platform import module_enabled

from .errors import ShopRefused
from .gates import require_feature, write_allowed
from .models import ShopEventOffer, ShopVariant

STAFF_EVENT_LIMIT = 50


def require_offers(space):
    # Events first: with it off `shop.event_pickup` reads off too, and the owner of the switch is what to name.
    if not module_enabled(space, "events"):
        raise ShopRefused("feature_off", gettext("Events are switched off for this space."), feature="events")
    require_feature(space, "shop.event_pickup")
    return space


def _staff_events(space, actor):
    """Upcoming published events, plus the drafts `actor` may see as events staff.

    A draft is the events area's unpublished work: shop staff without event authority see
    only published events, so the offer list never discloses a draft's title or date.
    """
    from django.db.models import Q

    from apps.events import event_authority, event_permissions
    from apps.events.models import Event

    upcoming = Event.objects.filter(makerspace=space, ends_at__gt=timezone.now())
    drafts = event_authority.events_for(actor, event_permissions.VIEW, upcoming.filter(status=Event.Status.DRAFT))
    return upcoming.filter(Q(status=Event.Status.PUBLISHED) | Q(pk__in=drafts.values("pk")))


def staff_rows(space, actor):
    """Upcoming events of this space, each with the variant ids it offers."""
    require_offers(space)
    events = list(_staff_events(space, actor).order_by("starts_at", "pk")[:STAFF_EVENT_LIMIT])
    offered = {}
    for event_id, variant_id in ShopEventOffer.objects.filter(makerspace=space, event__in=events).values_list(
            "event_id", "variant_id"):
        offered.setdefault(event_id, []).append(variant_id)
    return [{"id": event.pk, "title": event.title, "starts_at": event.starts_at, "status": event.status,
             "variant_ids": offered.get(event.pk, [])} for event in events]


def _variants(space, variant_ids):
    ids = list(dict.fromkeys(int(value) for value in variant_ids))
    rows = {row.pk: row for row in ShopVariant.objects.filter(
        makerspace=space, pk__in=ids, is_active=True, archived_at__isnull=True,
        product__archived_at__isnull=True, product__is_active=True)}
    if len(rows) != len(ids):
        raise ShopRefused("variant_invalid", gettext("Choose live items from this shop."))
    return ids


def set_offers(space, event_id, variant_ids, *, actor):
    """Replace one event's offer list (order = the given order). Returns the saved variant ids."""
    from apps.makerspaces.guards import require_module_locked

    with transaction.atomic():
        space = require_module_locked(space, "shop")
        write_allowed(space)
        require_offers(space)
        event = _staff_events(space, actor).filter(pk=event_id).select_for_update().first()
        if event is None:
            raise ShopRefused("pickup_event_invalid", gettext("Choose one of this space's upcoming events."))
        ids = _variants(space, variant_ids)
        current = {row.variant_id: row for row in ShopEventOffer.objects.filter(event=event)}
        removed = [pk for pk in current if pk not in ids]
        ShopEventOffer.objects.filter(event=event, variant_id__in=removed).delete()
        added = 0
        for index, variant_id in enumerate(ids):
            row = current.get(variant_id)
            if row is None:
                ShopEventOffer.objects.create(makerspace=space, event=event, variant_id=variant_id, sort_order=index)
                added += 1
            elif row.sort_order != index:
                row.sort_order = index
                row.save(update_fields=["sort_order"])
        if added or removed:
            audit.record(actor, "shop.event_offers_set", makerspace=space, target=event, meta={
                "event_id": event.pk, "variant_count": len(ids), "added": added, "removed": len(removed)})
    return ids


def public_offers(space, token):
    """The event (by its public token) and the public products it offers, offered variants only."""
    from apps.events.website_visibility import public_events
    from apps.makerspaces.editions import require_public_surface

    from .public import product_payload, public_products

    require_offers(space)
    require_public_surface("events")
    event = public_events(space).filter(public_token=token, ends_at__gt=timezone.now()).first()
    if event is None:
        raise ShopRefused("not_found", gettext("This event has no shop items."))
    offered = list(ShopEventOffer.objects.filter(makerspace=space, event=event).values_list("variant_id", flat=True))
    products = []
    for product in public_products(space).filter(variants__pk__in=offered).distinct():
        payload = product_payload(space, product)
        payload["variants"] = [row for row in payload["variants"] if row["id"] in offered]
        if not payload["variants"]:
            continue
        prices = [row["price"] for row in payload["variants"] if row["price"] is not None]
        payload.update(price_from=min(prices) if prices else None, price_to=max(prices) if prices else None,
                       sold_out=all(row["sold_out"] for row in payload["variants"]))
        products.append(payload)
    from apps.payments.models import MakerspacePaymentSettings

    return {"event": {"id": event.pk, "title": event.title, "starts_at": event.starts_at},
            "currency": MakerspacePaymentSettings.for_makerspace(space).default_currency, "products": products}

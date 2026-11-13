"""Shop notices (release 2 L22): the buyer's order messages and the shop staff's alerts.

A buyer with an account hears through their own channels (an envelope under the
`payments` matrix); a guest gets one direct email carrying only their own signed status
link. Staff alerts (a new online order, an order the stock could not fill, low stock) go
to the people holding `manage_shop` in that space -- the Shop Manager and the Space
Manager -- never to anyone without shop authority. No message carries another person's
details. Refund decisions reach an account buyer through the refund-case notices.

Family (open items A33/C29, a recorded decision): shop notices are STORED and ROUTED under the
`payments` family on purpose -- one matrix, one set of destinations, one preference row per channel,
the same `payments` event keys every template and webhook binding already uses. "Shop" is a display
family the inbox carves out at read time (`notifications/inbox_families.py`), so the inbox filter and
the chip say Shop. Consequence to know: muting the Payments channel cell mutes shop alerts too; a space
that wants shop silent alone mutes the `shop_*` events in the per-event matrix.
"""

from django.utils.translation import gettext, gettext_noop

from apps.integrations.notification_outbox import emit
from apps.integrations.notification_sources import NotificationSource, register_source
from config.locale_resolution import override_for
from apps.operations.notifications_p2 import body, direct_mail_unless_routed, fanout, revision, safe_notification

SOURCE = "shop.order"
STOCK_SOURCE = "shop.stock"
BUYER_EVENTS = ("shop_order_placed", "shop_order_paid", "shop_order_ready", "shop_order_lapsed",
                "shop_order_cancelled", "shop_order_unfulfilled", "shop_order_reminder", "shop_order_receipt",
                "shop_order_pickup_moved_to_space", "shop_order_collected")
STAFF_EVENTS = ("shop_order_new", "shop_order_unfulfilled", "shop_low_stock")
STATUS_SALT = "spaceworks.shop-order-status"


def status_token(order):
    from django.core import signing
    return signing.dumps([order.pk, order.status_secret[:24]], salt=STATUS_SALT)


def order_for_token(token, **lookup):
    import hmac

    from django.core import signing

    from .models import ShopOrder

    if not token or len(token) > 200:
        return None
    try:
        order_id, secret = signing.loads(token, salt=STATUS_SALT)
    except (signing.BadSignature, TypeError, ValueError):
        return None
    order = ShopOrder.objects.select_related("makerspace", "pickup_event").filter(pk=order_id, **lookup).first()
    if order is None or not hmac.compare_digest(order.status_secret[:24], str(secret)):
        return None
    return order


def _copy(order, event):
    from .pickup_status import pickup_requires_staff_confirmation

    space = order.makerspace
    v = {"id": order.pk, "ref": gettext("#%(id)s (pickup code %(code)s)") % {"id": order.pk, "code": order.pickup_code},
         "amount": f"{order.currency.upper()} {order.amount_due}", "space": space.name}
    if event in {"shop_order_placed", "shop_order_paid", "shop_order_ready", "shop_order_reminder"} and (
        pickup_requires_staff_confirmation(order)
    ):
        handoff = gettext("Your event pickup is unavailable. Contact %(space)s to confirm where to collect your order.") % v
        if event == "shop_order_paid":
            handoff = gettext("We received %(amount)s for order #%(id)s. %(handoff)s") % {**v, "handoff": handoff}
        return gettext("Confirm pickup for order #%(id)s") % v, handoff
    v["place"] = gettext("at the space") if order.pickup_at == "space" else gettext("at the event you chose")
    if event == "shop_order_placed":
        tail = (gettext("Pay at the desk when you collect it.") if order.status == "awaiting_payment"
                else gettext("Finish paying online to confirm it."))
        return (gettext("Your order at %(space)s") % v,
                gettext("Thanks for your order %(ref)s of %(amount)s.") % v + " " + tail)
    return {
        "shop_order_paid": lambda: (gettext("Order %(ref)s is paid") % v,
                                    gettext("We received %(amount)s for order %(ref)s. We will tell you when "
                                            "it is ready to collect %(place)s.") % v),
        "shop_order_ready": lambda: (gettext("Order %(ref)s is ready") % v,
                                     gettext("Your order %(ref)s is ready to collect %(place)s. Bring the "
                                             "pickup code.") % v),
        "shop_order_pickup_moved_to_space": lambda: (
            gettext("Pickup changed for order #%(id)s") % v,
            gettext("Order #%(id)s will be collected at %(space)s. Check your order for payment and pickup "
                    "status.") % v),
        # Decision 221(f): the handed-over confirmation (the shop's "delivered" notice for pickup orders).
        "shop_order_collected": lambda: (gettext("Order #%(id)s was handed over") % v,
                                         gettext("Order #%(id)s was collected. Thank you for shopping at "
                                                 "%(space)s.") % v),
        "shop_order_lapsed": lambda: (gettext("Order %(ref)s was released") % v,
                                      gettext("Order %(ref)s was not paid in time, so its items went "
                                              "back on sale.") % v),
        "shop_order_cancelled": lambda: (gettext("Order %(ref)s was cancelled") % v,
                                         gettext("Order %(ref)s was cancelled because it was not "
                                                 "collected. Staff will review your refund.") % v),
        "shop_order_unfulfilled": lambda: (gettext("Order %(ref)s could not be filled") % v,
                                           gettext("Sorry, an item in order %(ref)s sold out "
                                                   "before payment. Staff will review your refund.") % v),
        "shop_order_reminder": lambda: (gettext("Order %(ref)s is waiting for you") % v,
                                        gettext("Your order %(ref)s is waiting to be collected "
                                                "%(place)s.") % v),
        "shop_order_receipt": lambda: (gettext("Your receipt from %(space)s") % v,
                                       gettext("Thank you. Order %(ref)s: %(amount)s paid.") % v),
    }[event]()


@safe_notification
def buyer_notice(order, event, marker=None):
    from apps.makerspaces.website_directory import public_url

    from apps.makerspaces.platform import module_enabled

    if event not in BUYER_EVENTS:
        raise ValueError("Unknown shop buyer notice")
    space = order.makerspace
    if not module_enabled(space, "shop"):  # decision 253(a): no envelope while Shop is off
        return None
    marker = marker or order.status
    if order.buyer_id:
        return fanout(row=order, space=space, feature="payments", stream="payments", event=event, source_kind=SOURCE,
                      revision=revision("ShopOrder", order.pk, event, marker), owner=order.buyer,
                      owner_body=lambda: body(*_copy(order, event)), staff=False, context={"order_id": order.pk})
    if not order.guest_email:
        return None
    link = public_url(space, "shop/order", status_token(order))
    with override_for(makerspace=space):  # a guest has no account: the space's default language
        subject, text = (str(part) for part in _copy(order, event))
    return direct_mail_unless_routed(space=space, source_kind=SOURCE, row=order, revision=str(marker), event=event,
                                     owner=None, to_email=order.guest_email, subject=subject,
                                     text=f"{text}\n\n{link}", stream="payments", audience="requester",
                                     feature="payments", persist_body=False, address_owner=False)


def shop_staff(space):
    from apps.accounts import rbac
    from apps.accounts.models import User
    from apps.makerspaces.models import MakerspaceMembership

    ids = MakerspaceMembership.staff_tracks.filter(
        makerspace=space, status="active", receives_notifications=True, user__is_active=True,
        user__access_status=User.AccessStatus.ACTIVE).values_list("user_id", flat=True)[:200]
    people = User.objects.filter(pk__in=list(ids)).exclude(is_superuser=True).order_by("pk")
    return [person for person in people if rbac.can(person, rbac.Action.MANAGE_SHOP, space.pk)]


@safe_notification
def staff_notice(space, row, event, *, text=""):
    from apps.integrations.notification_links import local_link

    from apps.makerspaces.platform import module_enabled

    if event not in STAFF_EVENTS:
        raise ValueError("Unknown shop staff notice")
    if not module_enabled(space, "shop"):  # decision 253(a): no envelope while Shop is off
        return None
    source = STOCK_SOURCE if event == "shop_low_stock" else SOURCE
    subjects = {"shop_order_new": gettext_noop("New shop order"),
                "shop_order_unfulfilled": gettext_noop("A paid shop order could not be filled"),
                "shop_low_stock": gettext_noop("Shop stock is low")}
    given = text
    key = revision(type(row).__name__, row.pk, event, getattr(row, "status", ""))
    for person in shop_staff(space):
        emit(makerspace=space, recipient=person, feature="payments", stream="payments", event=event, audience="staff",
             dedup_key=f"shop:{key}:{person.pk}", source_kind=source, source_id=str(row.pk), revision=key[:64],
             subject=row, context={"row_id": row.pk, "notice": event},
             rendered=lambda: body(
                 gettext(subjects[event]),
                 given or (gettext("Order #%(id)s needs attention in the shop.") % {"id": row.pk} if source == SOURCE else ""),
                 local_link(space, "admin", "shop")))
    return True


def eligible(envelope):
    from apps.accounts import rbac
    from apps.makerspaces.platform import module_enabled
    from apps.makerspaces.servability import is_servable

    from .models import ShopOrder, ShopVariant

    model = ShopVariant if envelope.source_kind == STOCK_SOURCE else ShopOrder
    row = model.objects.select_related("makerspace").filter(
        pk=envelope.source_id, makerspace_id=envelope.makerspace_id).first()
    if row is None or not is_servable(row.makerspace) or not module_enabled(row.makerspace, "shop"):
        return False
    if envelope.audience == "staff":
        return envelope.event in STAFF_EVENTS and rbac.can(envelope.recipient, rbac.Action.MANAGE_SHOP,
                                                           row.makerspace_id)
    return model is ShopOrder and envelope.event in BUYER_EVENTS and row.buyer_id == envelope.recipient_id


def register():
    register_source(SOURCE, NotificationSource(eligible))
    register_source(STOCK_SOURCE, NotificationSource(eligible))

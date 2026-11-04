"""Shop notices (release 2 L22): the buyer's order messages and the shop staff's alerts.

A buyer with an account hears through their own channels (an envelope under the
`payments` matrix); a guest gets one direct email carrying only their own signed status
link. Staff alerts (a new online order, an order the stock could not fill, low stock) go
to the people holding `manage_shop` in that space -- the Shop Manager and the Space
Manager -- never to anyone without shop authority. No message carries another person's
details. Refund decisions reach an account buyer through the refund-case notices.
"""

from apps.integrations.notification_outbox import emit
from apps.integrations.notification_sources import NotificationSource, register_source
from apps.operations.notifications_p2 import body, direct_mail_unless_routed, fanout, revision, safe_notification

SOURCE = "shop.order"
STOCK_SOURCE = "shop.stock"
BUYER_EVENTS = ("shop_order_placed", "shop_order_paid", "shop_order_ready", "shop_order_lapsed",
                "shop_order_cancelled", "shop_order_unfulfilled", "shop_order_reminder", "shop_order_receipt")
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
    order = ShopOrder.objects.filter(pk=order_id, **lookup).first()
    if order is None or not hmac.compare_digest(order.status_secret[:24], str(secret)):
        return None
    return order


def _copy(order, event):
    space, ref = order.makerspace, f"#{order.pk} (pickup code {order.pickup_code})"
    amount = f"{order.currency.upper()} {order.amount_due}"
    place = "at the space" if order.pickup_at == "space" else "at the event you chose"
    return {
        "shop_order_placed": (f"Your order at {space.name}", f"Thanks for your order {ref} of {amount}. "
                              + ("Pay at the desk when you collect it." if order.status == "awaiting_payment"
                                 else "Finish paying online to confirm it.")),
        "shop_order_paid": (f"Order {ref} is paid", f"We received {amount} for order {ref}. We will tell you when "
                                                    f"it is ready to collect {place}."),
        "shop_order_ready": (f"Order {ref} is ready", f"Your order {ref} is ready to collect {place}. Bring the "
                                                      "pickup code."),
        "shop_order_lapsed": (f"Order {ref} was released", f"Order {ref} was not paid in time, so its items went "
                                                          "back on sale."),
        "shop_order_cancelled": (f"Order {ref} was cancelled", f"Order {ref} was cancelled because it was not "
                                                               "collected. Staff will review your refund."),
        "shop_order_unfulfilled": (f"Order {ref} could not be filled", f"Sorry, an item in order {ref} sold out "
                                                                       "before payment. Staff will review your refund."),
        "shop_order_reminder": (f"Order {ref} is waiting for you", f"Your order {ref} is waiting to be collected "
                                                                   f"{place}."),
        "shop_order_receipt": (f"Your receipt from {space.name}", f"Thank you. Order {ref}: {amount} paid."),
    }[event]


@safe_notification
def buyer_notice(order, event, marker=None):
    from apps.makerspaces.website_directory import public_url

    if event not in BUYER_EVENTS:
        raise ValueError("Unknown shop buyer notice")
    space = order.makerspace
    subject, text = _copy(order, event)
    marker = marker or order.status
    if order.buyer_id:
        return fanout(row=order, space=space, feature="payments", stream="payments", event=event, source_kind=SOURCE,
                      revision=revision("ShopOrder", order.pk, event, marker), owner=order.buyer,
                      owner_body=body(subject, text), staff=False, context={"order_id": order.pk})
    if not order.guest_email:
        return None
    link = public_url(space, "shop/order", status_token(order))
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

    if event not in STAFF_EVENTS:
        raise ValueError("Unknown shop staff notice")
    source = STOCK_SOURCE if event == "shop_low_stock" else SOURCE
    subject = {"shop_order_new": "New shop order", "shop_order_unfulfilled": "A paid shop order could not be filled",
               "shop_low_stock": "Shop stock is low"}[event]
    text = text or (f"Order #{row.pk} needs attention in the shop." if source == SOURCE else "")
    key = revision(type(row).__name__, row.pk, event, getattr(row, "status", ""))
    for person in shop_staff(space):
        emit(makerspace=space, recipient=person, feature="payments", stream="payments", event=event, audience="staff",
             dedup_key=f"shop:{key}:{person.pk}", source_kind=source, source_id=str(row.pk), revision=key[:64],
             subject=row, context={"row_id": row.pk, "notice": event},
             rendered=body(subject, text, local_link(space, "admin", "shop")))
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

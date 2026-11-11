"""Online orders (`shop.online`): quote -> hold -> one Payment -> the rail or "pay at the desk".

Inside the space lock the basket is re-quoted, checked against the digest the buyer saw
(409 `price_changed`) and frozen on the order. With `shop.holds` on its stock is held for
the online window (Q-S4: 15 minutes) or, for a pay-at-desk order, for 48 hours; with it
off the stock is only checked here and taken when payment lands. Every sale is a charge
(`charges.shop`); the online card/UPI rail is put on top only with `payments.shop` and
credentials. A free basket is paid at once. Pickup only (Q-S3): at the space, or at one
of its events with `shop.event_pickup` on.
"""

import logging
from dataclasses import dataclass
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.makerspaces.platform import feature_enabled

from .errors import ShopRefused, out_of_stock
from .gates import online_rail, require_charges, require_feature, write_allowed
from .models import ShopOrder, ShopSettings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Buyer:
    account: object
    name: str
    email: str
    actor: object

    @property
    def is_guest(self):
        return self.account is None


def buyer_for(request, space, data):
    """The signed-in person, else (with `shop.guest_checkout`) a guest with a confirmed email (#80)."""
    user = request.user
    if getattr(user, "is_authenticated", False) and getattr(user, "account_kind", None) == "member" and user.is_active:
        name = (user.get_full_name() or getattr(user, "display_name", "") or user.username).strip()
        return Buyer(account=user, name=name[:200], email=(user.email or "")[:254], actor=user)
    if not feature_enabled(space, "shop.guest_checkout"):
        raise ShopRefused("guest_identity_required", "Sign in to order from this shop.")
    name, email, code = (str(data.get(key) or "").strip() for key in ("guest_name", "guest_email", "email_code"))
    if not name or not email or not code:
        raise ShopRefused("guest_identity_required", "Sign in, or give your name, email and the code we emailed you.")
    from apps.hardware_requests.contact_verification import consume_code, normalize_email
    from apps.makerspaces.anonymous_requesters import get_or_create_anonymous_requester

    consume_code(space, email, code)
    return Buyer(account=None, name=name[:200], email=normalize_email(email)[:254],
                 actor=get_or_create_anonymous_requester(space))


def send_code(space, email):
    from apps.hardware_requests.contact_verification import issue_code

    require_feature(space, "shop.guest_checkout")
    if "@" not in str(email or ""):
        raise ShopRefused("guest_identity_required", "Enter a valid email address.")
    issue_code(space, email)


def pickup_choice(space, data):
    """(pickup_at, event) -- the space, or an upcoming public event of this space."""
    if (data.get("pickup_at") or "space") != "event":
        return ShopOrder.Pickup.SPACE, None
    require_feature(space, "shop.event_pickup")
    from apps.events.models import Event

    event = Event.objects.filter(pk=data.get("pickup_event_id"), makerspace=space, status=Event.Status.PUBLISHED,
                                 ends_at__gt=timezone.now()).first()
    if event is None:
        raise ShopRefused("pickup_event_invalid", "Choose one of this space's upcoming events.")
    return ShopOrder.Pickup.EVENT, event


def _window(space, rail):
    row = ShopSettings.for_makerspace(space)
    return timedelta(minutes=row.online_hold_minutes) if rail else timedelta(hours=row.desk_hold_hours)


def _prior_order(space, buyer, key):
    """`(order, payment)` already placed under this key by the same buyer, else None."""
    from .orders_core import order_payment

    prior = ShopOrder.objects.filter(makerspace=space, idempotency_key=key).first()
    if prior is None:
        return None
    same = prior.buyer_id == getattr(buyer.account, "pk", None) and (
        not buyer.is_guest or (prior.guest_email or "").lower() == (buyer.email or "").lower())
    if not same:
        raise ShopRefused("idempotency_key_reused", "That Idempotency-Key belongs to another order.")
    return prior, order_payment(prior)


def place_online_order(space, buyer, data, *, idempotency_key=""):
    """Returns `(order, payment)`; the caller adds the hosted checkout after commit.

    A client `Idempotency-Key` makes a double submit return the FIRST order (and its charge):
    looked up before any work, and backed by a unique constraint so two simultaneous
    submits cannot both insert (the loser re-reads the winner).
    """
    key = (idempotency_key or "").strip()[:64]
    if key:
        prior = _prior_order(space, buyer, key)
        if prior is not None:
            return prior
    try:
        return _place_online_order(space, buyer, data, key)
    except IntegrityError as exc:
        if key and "shop_order_idempotency_once" in str(exc):
            prior = _prior_order(space, buyer, key)
            if prior is not None:
                return prior
        raise


def _place_online_order(space, buyer, data, key):
    from apps.inventory.availability import OutOfStock, hold_shop_checkout, shop_sellable
    from apps.makerspaces.guards import require_module_locked
    from apps.payments.pricing import verify_digest

    from .notices import buyer_notice, staff_notice
    from .orders_core import create_order, raise_charge
    from .pricing import priced_basket
    from .settlement import settle_locked

    with transaction.atomic():
        space = require_module_locked(space, "shop")
        write_allowed(space)
        require_feature(space, "shop.online")
        require_charges(space)
        basket = priced_basket(space, data.get("lines"), person=buyer.account, public=True, lock=True)
        verify_digest(basket.quote, data.get("quote_digest") or None)
        pickup_at, event = pickup_choice(space, data)
        rail = online_rail(space) and basket.quote.total > 0
        status = ShopOrder.Status.HELD if rail else ShopOrder.Status.AWAITING_PAYMENT
        expires_at = timezone.now() + _window(space, rail)
        order = create_order(space, basket, channel=ShopOrder.Channel.ONLINE, status=status, actor=buyer.actor,
                             buyer=buyer.account, guest_name=buyer.name if buyer.is_guest else "",
                             guest_email=buyer.email if buyer.is_guest else "", pickup_at=pickup_at,
                             pickup_event=event, expires_at=expires_at, idempotency_key=key)
        pairs = basket.stock_pairs()
        try:
            if feature_enabled(space, "shop.holds"):
                hold_shop_checkout(order, pairs, expires_at=expires_at)
            else:
                for variant, _quantity in basket.items:
                    if shop_sellable(variant, bundles=basket.bundles) < _quantity:
                        raise OutOfStock(variant.pk, shop_sellable(variant, bundles=basket.bundles))
        except OutOfStock as exc:
            raise out_of_stock(exc, basket.labels) from None
        payment = raise_charge(order, basket, actor=buyer.actor)
        audit.record(buyer.account, "shop.order_placed", makerspace=space, target=order, meta={
            "order_id": order.pk, "channel": "online", "total": str(order.total), "guest": buyer.is_guest,
            "rail": bool(rail), "pickup_at": pickup_at, "lines": len(basket.items)})
        if payment is None:
            settle_locked(order, actor=None)
        else:
            buyer_notice(order, "shop_order_placed")
            staff_notice(space, order, "shop_order_new")
    return order, payment


def checkout_url(payment):
    """The hosted checkout for the order's charge, or "" (pay at the desk; the debt is kept)."""
    from apps.payments.services import create_checkout_url

    if payment is None or payment.status != "pending" or not online_rail(payment.makerspace):
        return ""
    try:
        return create_checkout_url(payment.pk) or ""
    except Exception:  # noqa: BLE001 - a provider failure never loses the recorded order
        logger.warning("shop_checkout_failed", extra={"payment_id": payment.pk})
        return ""

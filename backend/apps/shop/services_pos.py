"""The front desk (`SELL_SHOP`): a sale paid and handed over at once, and desk payment for an
online "pay at the desk" order.

Payment at the desk is cash, UPI (L5's UPI QR for the exact amount) or a card on an external
terminal (#76: no terminal integration). Each is recorded as an offline `ManualSettlement`
(method, reference, received date) in the SAME transaction as the sale, through the
ledger's `apply_reconciliation`, which also issues the L5 receipt. The two-person check
(`billing.maker_checker`) applies to the cash-up, not to each sale (Q-S19), so a desk sale
never waits for a checker. With `shop.cash_up` on, a cash sale needs an open cash session
and belongs to it.
"""

from django.utils.translation import gettext
from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.makerspaces.platform import feature_enabled

from .errors import ShopRefused, out_of_stock
from .gates import require_charges, write_allowed
from .models import ShopCashSession, ShopOrder

DESK_METHODS = ("cash", "upi", "card_machine")


def open_session(space):
    return ShopCashSession.objects.select_for_update().filter(makerspace=space).exclude(
        status=ShopCashSession.Status.CLOSED).first()


def _session_for(space, method):
    if method != "cash" or not feature_enabled(space, "shop.cash_up"):
        return None
    session = open_session(space)
    if session is None or session.status != ShopCashSession.Status.OPEN:
        raise ShopRefused("cash_session_closed", gettext("Open the cash drawer (a cash session) before taking cash."))
    return session


def _settle(payment, actor, settlement):
    """Lock the charge and record the desk receipt with it (no maker-checker: Q-S19)."""
    from apps.payments.models import Payment
    from apps.payments.reconciliation import apply_reconciliation

    locked = Payment.objects.select_for_update(of=("self",)).select_related("makerspace").get(pk=payment.pk)
    if locked.status != Payment.Status.PENDING:
        raise ShopRefused("order_not_payable", gettext("This charge is already settled."))
    return apply_reconciliation(locked, actor, Payment.Status.PAID_OFFLINE, settlement)


def _receipt(payment, method, reference, received_at):
    return {"method": method, "reference": (reference or "")[:64], "received_at": received_at or timezone.now()}


def _paid_and_collected(order, actor):
    now = timezone.now()
    order.status, order.paid_at, order.collected_at, order.collected_by = (
        ShopOrder.Status.COLLECTED, now, now, actor)
    order.save(update_fields=["status", "paid_at", "collected_at", "collected_by"])


def pos_sale(space, *, actor, lines, member=None, method="cash", reference="", received_at=None, digest=None,
             receipt_email=""):
    """A desk sale: priced, sold from stock now, paid offline and handed over. Returns the order."""
    from apps.inventory.availability import OutOfStock, sell_shop_stock
    from apps.makerspaces.guards import require_module_locked
    from apps.payments.pricing import verify_digest

    from .orders_core import create_order, raise_charge
    from .pricing import priced_basket

    if method not in DESK_METHODS:
        raise ShopRefused("order_not_payable", gettext("Choose cash, UPI or card."))
    with transaction.atomic():
        space = require_module_locked(space, "shop")
        write_allowed(space)
        require_charges(space)
        basket = priced_basket(space, lines, person=member, public=False, lock=True)
        verify_digest(basket.quote, digest or None)
        session = _session_for(space, method)
        order = create_order(space, basket, channel=ShopOrder.Channel.POS, status=ShopOrder.Status.AWAITING_PAYMENT,
                             actor=actor, buyer=basket.member, guest_email=receipt_email if not basket.member else "")
        payment = raise_charge(order, basket, actor=actor)
        order = ShopOrder.objects.select_for_update().get(pk=order.pk)
        try:
            sell_shop_stock(order, basket.stock_pairs(), actor=actor, reason=f"Desk sale #{order.pk}")
        except OutOfStock as exc:
            raise out_of_stock(exc, basket.labels) from None
        from .consumable_costs import record_sale_costs
        record_sale_costs(order, actor=actor)
        _paid_and_collected(order, actor)
        if payment is not None:
            _settle(payment, actor, _receipt(payment, method, reference, received_at))
        if session is not None:
            ShopOrder.objects.filter(pk=order.pk).update(cash_session=session)
        audit.record(actor, "shop.pos_sale", makerspace=space, target=order, meta={
            "order_id": order.pk, "total": str(order.amount_due), "method": method if payment else "free",
            "member": basket.member is not None, "cash_session_id": getattr(session, "pk", None)})
    order.refresh_from_db()
    return order


def collect_payment(order, *, actor, method="cash", reference="", received_at=None, hand_over=True):
    """Take payment at the desk for an online pay-at-desk order, then (usually) hand it over."""
    from .orders_core import order_payment
    from .settlement import settle_locked

    if method not in DESK_METHODS:
        raise ShopRefused("order_not_payable", gettext("Choose cash, UPI or card."))
    with transaction.atomic():
        order = ShopOrder.objects.select_for_update().select_related("makerspace").get(pk=order.pk)
        write_allowed(order.makerspace)
        if order.status not in ShopOrder.OPEN_STATUSES:
            raise ShopRefused("order_not_payable", gettext("This order is not waiting for payment."), status=order.status)
        from .pickup_status import pickup_requires_staff_confirmation
        if hand_over and pickup_requires_staff_confirmation(order):  # decision 221(h), as collect() refuses
            raise ShopRefused("pickup_interrupted", gettext("This order's event pickup was interrupted. Move the pickup to "
                                                    "the space before handing it over."))
        payment = order_payment(order)
        if payment is None:
            raise ShopRefused("order_not_payable", gettext("This order has nothing to pay."))
        session = _session_for(order.makerspace, method)
        _settle(payment, actor, _receipt(payment, method, reference, received_at))
        settle_locked(order, actor=actor, collect=hand_over)
        if session is not None:
            ShopOrder.objects.filter(pk=order.pk).update(cash_session=session)
        audit.record(actor, "shop.order_paid_at_desk", makerspace=order.makerspace, target=order, meta={
            "order_id": order.pk, "method": method, "handed_over": hand_over,
            "cash_session_id": getattr(session, "pk", None)})
    order.refresh_from_db()
    if hand_over and order.status == ShopOrder.Status.COLLECTED:
        # m10 / decision 221(h): a desk hand-over tells the buyer and signed destinations exactly as `collect()`.
        from .notices import buyer_notice
        from .webhooks import handover_event, order_webhook
        buyer_notice(order, "shop_order_collected")
        order_webhook(order, handover_event(order))
    return order

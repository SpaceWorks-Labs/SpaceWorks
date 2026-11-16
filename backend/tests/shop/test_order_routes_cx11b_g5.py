"""Every staff order/POS/cash route asserts its persisted state and exact owner audit."""
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.shop.checkout import Buyer, place_online_order
from apps.shop.models import ShopCashSession, ShopOrder, ShopStockMovement
from apps.shop.orders_core import order_payment
from apps.shop.services_cash import close_cash, open_cash
from apps.shop.services_pos import pos_sale
from tests.payments.route_support_cx11b_g5 import cycle, hidden, ids, world
from tests.shop.helpers import line
from tests.shop.route_fixtures_cx11b_g5 import seed

pytestmark = [pytest.mark.django_db, pytest.mark.area_shop, pytest.mark.area_payments_ledger]
OPS = (
    ("orders", "GET", ()), ("order", "GET", ()), ("order-ready", "POST", ()),
    ("order-move-pickup-to-space", "POST", ()), ("order-collect", "POST", ()),
    ("order-take-payment", "POST", ()), ("order-cancel", "POST", ()),
    ("order-returns", "POST", ("shop.returns",)), ("order-receipt", "GET", ("shop.receipts",)),
    ("order-receipt", "POST", ("shop.receipts",)),
    ("pos-quote", "POST", ("charges.enabled", "charges.shop")),
    ("pos-sale", "POST", ("charges.enabled", "charges.shop")),
    ("member-lookup", "GET", ()), ("report", "GET", ()),
    ("cash-sessions", "GET", ("shop.cash_up",)), ("cash-sessions", "POST", ("shop.cash_up",)),
    ("cash-session-close", "POST", ("shop.cash_up",)), ("cash-session-confirm", "POST", ("shop.cash_up",)),
)
CASES = [(suffix, method, key, native) for suffix, method, keys in OPS
         for key in ("shop", *keys) for native in (False, True)]


@pytest.mark.parametrize("suffix,method,key,native", CASES)
def test_staff_order_route_effect_standing_off_fence_and_restore(suffix, method, key, native):
    s = seed(native)
    basket = [line(s.variant)]
    cash = None
    if not (suffix == "cash-sessions" and method == "POST"):
        cash = open_cash(s.space, actor=s.actor, opening_float="10.00")
    unpaid = suffix in {"order-cancel", "order-take-payment"}
    order = None
    if suffix.startswith("order") or suffix == "report":
        if unpaid:
            order, _ = place_online_order(s.space, Buyer(s.buyer, "G5 buyer", "g5@example.test", s.buyer), {"lines": basket})
        else:
            order = pos_sale(s.space, actor=s.actor, member=s.buyer, lines=basket, method="cash", reference="G5-SEED")
            if suffix in {"order-ready", "order-collect", "order-move-pickup-to-space"}:
                ShopOrder.objects.filter(pk=order.pk).update(status="paid", collected_at=None, collected_by=None)
    if suffix == "order-move-pickup-to-space":
        from tests.events.checkin_helpers import make_event
        event = make_event(s.space, status="cancelled")
        ShopOrder.objects.filter(pk=order.pk).update(channel="online", pickup_at="event", pickup_event=event)
    if suffix == "cash-session-confirm":
        s.space.enabled_features += ["billing.maker_checker"]
        s.space.save(update_fields=["enabled_features"])
        # The second person is the caller; the original cashier proposes the close.
        close_cash(cash, actor=s.buyer, counted_cash="10.00", note="G5 counted")
    kwargs = {"makerspace_id": s.space.pk} if suffix in {
        "orders", "pos-quote", "pos-sale", "member-lookup", "report", "cash-sessions"} else {
        "pk": cash.pk if suffix.startswith("cash-session") else order.pk}
    body, audit, on = {}, (), (200, None)
    if suffix == "order-collect":
        body, audit = {"pickup_code": order.pickup_code}, ("shop.order_collected",)
    elif suffix == "order-ready":
        audit = ("shop.order_ready",)
    elif suffix == "order-move-pickup-to-space":
        audit = ("shop.order_pickup_moved_to_space",)
    elif suffix == "order-take-payment":
        body, audit = {"method": "cash", "reference": "G5-DESK"}, ("shop.order_paid", "shop.order_paid_at_desk")
    elif suffix == "order-cancel":
        audit = ("shop.order_cancelled",)
    elif suffix == "order-returns":
        body = {"rows": [{"line_id": order.lines.get().pk, "quantity": 1, "disposition": "restock"}], "reason": "G5 return"}
        audit = ("shop.stock_returned", "shop.refund_requested")
    elif suffix == "order-receipt" and method == "POST":
        # Persist the supplied desk address as well as the receipt intent/audit.
        ShopOrder.objects.filter(pk=order.pk).update(buyer=None)
        body, audit, on = {"email": "receipt@example.test"}, ("shop.receipt_emailed",), (204, None)
    elif suffix.startswith("pos-"):
        body = {"lines": basket}
        if suffix == "pos-sale":
            body.update(method="cash", reference="G5-POS")
            audit, on = ("shop.pos_sale",), (201, None)
    elif suffix == "cash-sessions" and method == "POST":
        body, audit, on = {"opening_float": "15.00"}, ("shop.cash_session_opened",), (201, None)
    elif suffix == "cash-session-close":
        body, audit = {"counted_cash": "9.50", "note": "G5 counted"}, ("shop.cash_session_closed",)
    elif suffix == "cash-session-confirm":
        audit = ("shop.cash_session_closed",)
    url = reverse("admin-shop-" + suffix, kwargs=kwargs)
    if suffix == "member-lookup":
        url += "?q=g5-shop-buyer"

    def result(response):
        variant = type(s.variant).objects.get(pk=s.variant.pk)
        if suffix == "member-lookup":
            assert response.data == [{"id": s.buyer.pk, "name": "g5-shop-buyer"}]
        elif suffix == "report":
            assert response.data["totals"] == {"orders": 1, "sales": "12.50", "refunds": "0.00", "net": "12.50", "tax": "0.00"}
            assert response.data["top_items"] == [{"label": "Widget", "quantity": 1, "sales": "12.50"}]
        elif suffix == "pos-quote":
            assert Decimal(response.data["total"]) == Decimal("12.50")
            assert Decimal(response.data["lines"][0]["quantity"]) == Decimal("1")
            assert ShopOrder.objects.filter(makerspace=s.space).count() == 0
        elif suffix.startswith("cash-session"):
            row = ShopCashSession.objects.get(pk=response.data["id"]) if method == "POST" else cash
            if suffix == "cash-sessions" and method == "GET":
                assert ids(response) == [cash.pk]
                assert Decimal(response.data["results"][0]["opening_float"]) == Decimal("10")
            elif suffix == "cash-sessions":
                assert (row.status, row.opening_float, row.opened_by_id) == ("open", Decimal("15"), s.actor.pk)
                assert ShopCashSession.objects.filter(makerspace=s.space).count() == 1
            else:
                expected = Decimal("9.50") if suffix.endswith("close") else Decimal("10")
                assert (row.status, row.counted_cash, row.expected_cash, row.variance) == (
                    "closed", expected, Decimal("10"), expected - Decimal("10"))
                assert row.confirmed_by_id == s.actor.pk and row.closed_at is not None
        elif suffix == "pos-sale":
            made = ShopOrder.objects.get(pk=response.data["id"])
            assert (made.status, made.amount_due, made.collected_by_id) == ("collected", Decimal("12.50"), s.actor.pk)
            payment = order_payment(made)
            assert (payment.status, payment.amount, payment.provider) == ("paid_offline", Decimal("12.50"), "unclaimed")
            assert payment.manual_settlements.get().reference == "G5-POS"
            assert list(made.lines.values_list("variant_id", "quantity")) == [(s.variant.pk, 1)]
            assert variant.on_hand == 7
        else:
            saved = ShopOrder.objects.get(pk=order.pk)
            if suffix == "orders":
                assert ids(response) == [order.pk]
            elif suffix == "order":
                assert (response.data["id"], response.data["lines"][0]["variant_id"]) == (order.pk, s.variant.pk)
            elif suffix == "order-ready":
                assert saved.status == response.data["status"] == "ready" and saved.ready_at is not None
            elif suffix == "order-move-pickup-to-space":
                assert (saved.pickup_at, saved.pickup_event_id, saved.status) == ("space", None, "paid")
            elif suffix in {"order-collect", "order-take-payment"}:
                assert (saved.status, saved.collected_by_id, variant.on_hand) == ("collected", s.actor.pk, 7)
                if suffix == "order-take-payment":
                    assert order_payment(saved).manual_settlements.get().reference == "G5-DESK"
            elif suffix == "order-cancel":
                assert (saved.status, variant.held, variant.on_hand, order_payment(saved).status) == ("cancelled", 0, 8, "canceled")
            elif suffix == "order-returns":
                returned = saved.returns.get()
                assert (returned.quantity, returned.amount, returned.disposition, variant.on_hand) == (1, Decimal("12.50"), "restock", 8)
                assert returned.refund_case.due_amount == Decimal("12.50") and saved.status == "refunded"
                assert order_payment(saved).refunds.count() == 0
                assert ShopStockMovement.objects.filter(order=saved, kind="returned", quantity=1).count() == 1
            elif method == "POST":
                assert saved.guest_email == "receipt@example.test"
            else:
                assert response.data["order_id"] == order.pk and Decimal(response.data["total"]) == Decimal("12.50")
                assert response.data["lines"][0]["label"] == "Widget"

    w = world(s.space, s.client, url, method, body, on, audit, result,
              probes=[hidden(s.foreign)], audit_prefix="shop.")
    off = "shop_closed" if key == "shop" else "charges_off" if key.startswith("charges.") else "feature_off"
    cycle(w, key, (409 if key.startswith("charges.") and suffix == "pos-sale" else 404, off))

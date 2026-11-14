"""Seeded shop operations, both real staff transports, and optional money rails."""
import pytest
from django.urls import reverse

from apps.payments.models import MakerspacePaymentSettings
from apps.shop.models import ShopOrder, ShopSettings
from apps.shop.services_cash import open_cash
from apps.shop.services_pos import pos_sale
from tests.modules.switch_matrix_object_helpers import client_for
from tests.payments.switch_helpers_cx11b_p2 import route_cycle
from tests.shop.helpers import line, manager, product, shop_space, switch

pytestmark = [pytest.mark.django_db, pytest.mark.area_shop, pytest.mark.area_payments_ledger]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("operation", ["cash", "receipt", "return", "online", "selling"])
@pytest.mark.parametrize("module_off", [False, True])
def test_seeded_shop_switch_refuses_before_writes_and_restores_same_objects(native, operation, module_off):
    space = shop_space("p2-shop-route", "shop.cash_up", "shop.receipts", "shop.returns", "shop.online")
    seller = manager(space)
    client = client_for(seller, space, native)
    row, variant = product(space, seller, price="12.50", stock=8)
    MakerspacePaymentSettings.for_makerspace(space).save()
    ShopSettings.objects.get_or_create(makerspace=space)
    session = open_cash(space, actor=seller, opening_float="10.00")
    order = pos_sale(space, actor=seller, lines=[line(variant)], method="cash", reference="P2-OFFLINE")
    # The ledger and order are real: the payment rail is deliberately absent.
    switch(space, modules=())
    space.enabled_modules = [key for key in space.enabled_modules if key != "payments"]
    space.save(update_fields=["enabled_modules"])
    assert order.status == ShopOrder.Status.COLLECTED
    objects = {"product": row, "variant": variant, "order": order, "session": session}
    kwargs, method, body = {"pk": order.pk}, "get", None
    feature, name, off = {
        "cash": ("shop.cash_up", "admin-shop-cash-sessions", "feature_off"),
        "receipt": ("shop.receipts", "admin-shop-order-receipt", "feature_off"),
        "return": ("shop.returns", "admin-shop-order-returns", "feature_off"),
        "online": ("shop.online", "public-shop-product", "feature_off"),
        "selling": ("charges.shop", "admin-shop-pos-quote", "charges_off"),
    }[operation]
    if operation == "cash":
        kwargs = {"makerspace_id": space.pk}
    elif operation == "online":
        kwargs = {"makerspace_slug": space.slug, "product_slug": row.slug}
    elif operation == "return":
        method, body = "post", {"rows": [{"line_id": order.lines.get().pk, "quantity": 1,
                                         "disposition": "restock"}], "reason": "Retained return"}
    elif operation == "selling":
        kwargs, method, body = {"makerspace_id": space.pk}, "post", {"lines": [line(variant)]}
    key = "shop" if module_off else feature
    route_cycle(space, client, objects, key, reverse(name, kwargs=kwargs), method=method, body=body,
                off=(404, "shop_closed" if module_off else off))


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
def test_guest_checkout_switch_refuses_code_creation_before_any_sql_write(native, monkeypatch):
    space = shop_space("p2-shop-guest", "shop.online", "shop.guest_checkout")
    seller = manager(space)
    row, variant = product(space, seller)
    monkeypatch.setattr("apps.integrations.email.send_email_verification_otp", lambda *_args: True)
    # Only the mail port is replaced; challenge creation, throttling and audit remain real.
    route_cycle(space, client_for(seller, space, native), {"product": row, "variant": variant},
        "shop.guest_checkout", reverse("public-shop-email-code", kwargs={"makerspace_slug": space.slug}),
        method="post", body={"email": "buyer@example.test"}, on=(204, None), off=(404, "feature_off"))

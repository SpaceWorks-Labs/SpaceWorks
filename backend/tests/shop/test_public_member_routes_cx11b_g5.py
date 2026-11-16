"""Public/bearer and owner-filtered shop surfaces retain their distinct contracts."""
from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.shop.checkout import Buyer, place_online_order
from apps.shop.models import ShopEventOffer, ShopOrder
from apps.shop.orders_core import order_payment
from tests.events.checkin_helpers import make_event
from tests.payments.route_support_cx11b_g5 import cycle, hidden, ids, world
from tests.shop.helpers import line
from tests.shop.route_fixtures_cx11b_g5 import seed

pytestmark = [pytest.mark.django_db, pytest.mark.area_shop]
PUBLIC = [(name, method, keys) for name, method, keys in (
    ("public-shop", "GET", ()), ("public-shop-products", "GET", ()),
    ("public-shop-product", "GET", ()),
    ("public-shop-quote", "POST", ("charges.enabled", "charges.shop")),
    ("public-shop-email-code", "POST", ("shop.guest_checkout",)),
    ("public-shop-orders", "POST", ("charges.enabled", "charges.shop")),
    ("public-shop-order-status", "GET", ()),
    ("public-shop-event-offers", "GET", ("events", "shop.event_pickup")),
)]
CASES = [(name, method, key, native) for name, method, keys in PUBLIC
         for key in ("shop", "shop.online", *keys) for native in (False, True)]


@pytest.mark.parametrize("name,method,key,native", CASES)
def test_public_shop_route_seeded_result_and_independent_switches(name, method, key, native, monkeypatch):
    s = seed(native)
    kwargs, body, audit, on = {"makerspace_slug": s.space.slug}, {}, (), (200, None)
    basket = [line(s.variant)]
    event = order = None
    if name == "public-shop-product":
        kwargs["product_slug"] = s.product.slug
    if name in {"public-shop-quote", "public-shop-orders"}:
        body = {"lines": basket}
    if name == "public-shop-orders":
        audit, on = ("payment.created", "shop.order_placed"), (201, None)
    if name == "public-shop-email-code":
        from apps.makerspaces.anonymous_requesters import get_or_create_anonymous_requester
        get_or_create_anonymous_requester(s.space)
        monkeypatch.setattr("apps.integrations.email.send_email_verification_otp", lambda *_args: True)
        body, audit, on = {"email": "g5-buyer@example.test"}, ("request.contact_code_sent",), (204, None)
    if name == "public-shop-order-status":
        from apps.shop.notices import status_token
        order, _ = place_online_order(s.space, Buyer(None, "G5 guest", "guest@example.test", s.actor), {"lines": basket})
        kwargs["token"] = status_token(order)
    if name == "public-shop-event-offers":
        event = make_event(s.space)
        ShopEventOffer.objects.create(makerspace=s.space, event=event, variant=s.variant)
        kwargs["public_token"] = event.public_token
    off = (409 if key.startswith("charges.") and name == "public-shop-orders" else 404,
           "shop_closed" if key == "shop" else "charges_off" if key.startswith("charges.") else "feature_off")

    def result(response):
        data = response.data
        if name == "public-shop":
            assert (data["name"], data["policy_text"], data["currency"]) == (s.space.name, "G5 retained policy", "inr")
            assert data["pay_online"] is False and data["hold_minutes"] == 15
        elif name in {"public-shop-products", "public-shop-product"}:
            row = data["results"][0] if name.endswith("products") else data
            assert (row["id"], row["variants"][0]["id"], row["name"]) == (s.product.pk, s.variant.pk, "Widget")
            assert row["price_from"] == Decimal("12.50") and row["sold_out"] is False
        elif name == "public-shop-quote":
            assert Decimal(data["total"]) == Decimal("12.50")
            assert data["lines"][0]["variant_id"] == s.variant.pk
        elif name == "public-shop-orders":
            saved = ShopOrder.objects.get(pk=data["order"]["id"])
            assert (saved.buyer_id, saved.status, saved.total) == (s.buyer.pk, "awaiting_payment", Decimal("12.50"))
            assert list(saved.lines.values_list("variant_id", "quantity")) == [(s.variant.pk, 1)]
            assert saved.holds.get().quantity == 1 and saved.holds.get().released_at is None
            payment = order_payment(saved)
            assert (payment.member_id, payment.provider, payment.amount) == (s.buyer.pk, "unclaimed", Decimal("12.50"))
            assert payment.pricing_snapshot["digest"] == saved.digest
        elif name == "public-shop-email-code":
            from apps.accounts.models import EmailVerificationChallenge
            from apps.hardware_requests.contact_verification import email_key
            challenge = EmailVerificationChallenge.objects.get(email=email_key(s.space, body["email"]))
            assert challenge.consumed_at is None and challenge.failed_attempts == 0
            assert challenge.code_digest and challenge.expires_at > challenge.last_sent_at
        elif name == "public-shop-order-status":
            assert (data["id"], data["status"], data["lines"][0]["variant_id"]) == (order.pk, "awaiting_payment", s.variant.pk)
        else:
            assert data["event"]["id"] == event.pk
            assert [r["id"] for r in data["products"]] == [s.product.pk]
            assert [r["id"] for r in data["products"][0]["variants"]] == [s.variant.pk]

    probes = []
    if name == "public-shop-order-status":
        bad = reverse(name, kwargs={**kwargs, "token": "forged"})
        # Public bearer contract: the shop gate is public; an invalid bearer never reveals an order.
        probes = [(lambda w: s.buyer_client.get(bad), lambda disabled: off if disabled else (404, "not_found"), lambda r: None)]
    elif name == "public-shop-orders":
        # No account or confirmed contact: the public contract is an identity refusal,
        # not staff tenant standing. A disabled public surface keeps its public gate.
        probes = [(lambda w: APIClient().post(w.url, body, format="json"),
                   lambda disabled: off if disabled else (
                       400, "guest_identity_required"), lambda r: None)]
    elif name not in {"public-shop-orders", "public-shop-email-code"}:
        def visitor(w):
            return APIClient().get(w.url) if method == "GET" else APIClient().post(w.url, body, format="json")
        probes = [(visitor, lambda disabled: off if disabled else on, lambda r: None)]
    # Public browse needs no tenant standing (481/494); buyer creation uses the signed-in person's own account.
    caller = APIClient() if name == "public-shop-email-code" and not native else s.buyer_client
    w = world(s.space, caller, reverse(name, kwargs=kwargs), method, body, on, audit, result, probes)
    cycle(w, key, off)


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("name,method", [("member-shop-orders", "GET"), ("member-shop-order", "GET"),
                                        ("member-shop-order-cancel", "POST")])
@pytest.mark.parametrize("key", ["shop", "shop.online", "charges.shop"])
def test_member_order_owner_and_other_person_before_during_after_switch(native, name, method, key):
    s = seed(native)
    if native:
        # These global owner-filtered member routes have no tenant selection contract.
        # Member APIs may omit the optional header; the real device token remains.
        for caller in (s.buyer_client, s.client, s.foreign):
            caller._credentials.pop("HTTP_X_MAKERSPACE_ID", None)
    order, _ = place_online_order(s.space, Buyer(s.buyer, "Buyer", "buyer@example.test", s.buyer), {"lines": [line(s.variant)]})
    kwargs = {} if name == "member-shop-orders" else {"pk": order.pk}
    listing = name == "member-shop-orders"
    def result(response):
        assert ids(response) == [order.pk] if listing else response.data["id"] == order.pk
        saved = ShopOrder.objects.get(pk=order.pk)
        assert saved.status == ("cancelled" if method == "POST" else "awaiting_payment")
        assert saved.lines.get().variant_id == s.variant.pk
        if method == "POST":
            assert saved.holds.get().release_reason == "cancelled"
            assert order_payment(saved).status == "canceled"
    def empty(response):
        assert response.data["results"] == [] and response.data["count"] == 0
    # 481/494/520: object non-owners see 404; collection scopes to the caller and returns an empty page.
    probes = [(caller, (200, None), empty) if listing else hidden(caller, (404, "not_found"))
              for caller in (s.client, s.foreign)]
    w = world(s.space, s.buyer_client, reverse(name, kwargs=kwargs), method,
              audit=("payment.canceled", "shop.order_cancelled") if method == "POST" else (), check=result, probes=probes)
    if listing:
        w.off_check = empty
    cycle(w, key, ((200, None) if listing else (404, "not_found")) if key == "shop" else None)


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("name,method", [("admin-shop-event-offers", "GET"), ("admin-shop-event-offer", "PUT")])
@pytest.mark.parametrize("key", ["shop", "events", "shop.event_pickup"])
def test_event_offer_route_result_each_parent_and_standing(native, name, method, key):
    s = seed(native)
    event = make_event(s.space)
    if method == "GET":
        ShopEventOffer.objects.create(makerspace=s.space, event=event, variant=s.variant)
    kwargs = {"makerspace_id": s.space.pk}
    if method == "PUT":
        kwargs["event_id"] = event.pk
    def result(response):
        assert list(ShopEventOffer.objects.filter(event=event).values_list("variant_id", flat=True)) == [s.variant.pk]
        assert response.data == {"variant_ids": [s.variant.pk]} if method == "PUT" else (
            response.data[0]["id"] == event.pk and response.data[0]["variant_ids"] == [s.variant.pk])
    w = world(s.space, s.client, reverse(name, kwargs=kwargs), method, {"variant_ids": [s.variant.pk]},
              audit=("shop.event_offers_set",) if method == "PUT" else (), check=result, probes=[hidden(s.foreign)])
    cycle(w, key, (404, "shop_closed" if key == "shop" else "feature_off"))


@pytest.mark.parametrize("key", ["shop", "shop.online", "shop.guest_checkout", "charges.enabled", "charges.shop"])
def test_guest_order_without_account_uses_real_email_proof_and_independent_switches(key, monkeypatch):
    from apps.accounts.models import EmailVerificationChallenge
    from apps.hardware_requests import contact_verification
    s = seed(False)
    email = "g5-guest-order@example.test"
    monkeypatch.setattr(contact_verification, "_generate_otp", lambda: "123456")
    monkeypatch.setattr("apps.integrations.email.send_email_verification_otp", lambda *_args: True)
    contact_verification.issue_code(s.space, email)
    challenge = EmailVerificationChallenge.objects.get(email=contact_verification.email_key(s.space, email))
    body = {"lines": [line(s.variant)], "guest_name": "G5 proven guest", "guest_email": email, "email_code": "123456"}
    def result(response):
        order = ShopOrder.objects.get(pk=response.data["order"]["id"])
        payment = order_payment(order)
        challenge.refresh_from_db()
        assert challenge.consumed_at is not None and challenge.failed_attempts == 0
        assert (order.buyer_id, order.guest_name, order.guest_email) == (None, "G5 proven guest", email)
        assert (payment.member_id, payment.amount, payment.provider) == (None, Decimal("12.50"), "unclaimed")
        assert order.holds.get().quantity == 1 and response.data["status_token"]
    off = (400, "guest_identity_required") if key == "shop.guest_checkout" else (
        409 if key.startswith("charges.") else 404,
        "shop_closed" if key == "shop" else "charges_off" if key.startswith("charges.") else "feature_off")
    # 481/494/520: an anonymous caller has no tenant standing and may use exactly its
    # confirmed-contact order. Native account ordering is covered above separately.
    w = world(s.space, APIClient(), reverse("public-shop-orders", kwargs={"makerspace_slug": s.space.slug}),
        "POST", body, (201, None), ("payment.created", "shop.order_placed"), result)
    def untouched(response):
        challenge.refresh_from_db()
        assert challenge.consumed_at is None and challenge.failed_attempts == 0
    w.off_check = untouched
    cycle(w, key, off)

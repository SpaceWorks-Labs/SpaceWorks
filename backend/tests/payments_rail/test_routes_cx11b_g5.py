"""All four in-scope rail routes: real persistence through stubbed vendor SDK calls."""
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.payments import pay_links
from apps.payments.models import Payment, Refund
from tests.l5_local.helpers import accountless
from tests.payments.ledger_fixtures_cx11b_g5 import seed
from tests.payments.route_support_cx11b_g5 import cycle, hidden, personal_client, world
from tests.payments_rail.ports_cx11b_g5 import configure

pytestmark = [pytest.mark.django_db, pytest.mark.area_payments]
CASES = [(name, key, native) for name in ("member-payment-checkout", "member-payment-mobile-intent", "pay-link-checkout")
    for key in ("payments", "payments.enabled", "payments.membership" if name.startswith("member-") else "payments.loans",
                "membership" if name.startswith("member-") else "billing.pay_links",
                *(("member_accounts",) if name.startswith("member-") else ()))
    for native in ((True,) if name.endswith("mobile-intent") else (False, True))]


@pytest.mark.parametrize("name,key,native", CASES)
def test_rail_route_creates_provider_handle_exactly_and_refuses_before_write_when_off(name, key, native, monkeypatch):
    s = seed(native)
    ports = configure(s, monkeypatch)
    payment = s.payment
    client, kwargs = s.payer_client, {"makerspace_id": s.space.pk, "payment_id": payment.pk}
    bearer = name == "pay-link-checkout"
    if bearer:
        payment = accountless(s.space, s.actor)
        link, token = pay_links.create_link(actor=s.actor, makerspace_id=s.space.pk, payment_id=payment.pk)
        kwargs = {"token": token}
    url = reverse(name, kwargs=kwargs)
    def result(response):
        saved = Payment.objects.get(pk=payment.pk)
        assert (saved.provider, saved.stripe_provider, saved.status) == ("stripe", "raw", "pending")
        assert saved.amount == payment.amount and saved.currency == "inr"
        if name.endswith("mobile-intent"):
            assert saved.stripe_payment_intent_id == "pi_g5" and saved.online_rail == "native_payment_intent"
            assert response.data == {"vendor": "stripe", "payment_id": saved.pk, "client_secret": "pi_g5_secret", "publishable_key": "pk_test_g5"}
            assert ports.calls[-1][0] == "intent" and ports.calls[-1][2]["amount"] == 10000
        else:
            assert (saved.external_order_id, saved.stripe_checkout_session_id, saved.online_rail) == ("cs_g5", "cs_g5", "checkout")
            assert response.data == {"checkout_url": "https://checkout.example.test/g5"}
            assert ports.calls[-1][2]["line_items"][0]["price_data"]["unit_amount"] == int(saved.amount * 100)
    if bearer:
        bad = reverse(name, kwargs={"token": "forged"})
        probes = [(lambda w: s.foreign.post(bad, {}, format="json"), (404, "pay_link_invalid"), lambda r: None)]
    else:
        # Same-space non-owner resolves no Payment; foreign native selection remains 403 (494/524).
        from tests.accounts.account_factories import make_membership
        make_membership(s.actor, s.space)
        other = personal_client(s.actor, s.space, native)
        probes = [hidden(other, (404, "not_found"))]
        probes.append(hidden(s.foreign, (403, "permission_denied") if native else (404, "not_found")))
        if name.endswith("mobile-intent"):
            # This route exists only for a device session; a browser keeps the exact
            # IsDeviceAccessToken refusal, including while its money switches are off.
            from rest_framework.test import APIClient
            from tests.accounts.reauth_helpers import force_recent_authenticate
            browser = APIClient()
            force_recent_authenticate(browser, s.payer)
            probes.append(hidden(browser, (403, "permission_denied")))
    audit = ("payment.mobile_intent_created",) if name.endswith("mobile-intent") else ("payment.checkout_created",)
    off = (404, "module_disabled") if key == "payments" and not bearer else (503, "payments_unavailable")
    if key == "billing.pay_links":
        off = (404, "pay_link_invalid")
    cycle(world(s.space, client, url, "POST", audit=audit, check=result, probes=probes), key, off)


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["payments", "payments.enabled", "payments.membership"])
def test_staff_online_refund_keeps_recorded_money_refundable_after_new_collection_switches_off(native, key, monkeypatch):
    s = seed(native)
    ports = configure(s, monkeypatch)
    # A terminal charge keeps the provider it was captured through (never unclaimed).
    Payment.objects.filter(pk=s.payment.pk).update(provider="stripe", stripe_provider="raw",
        stripe_payment_intent_id="pi_captured_g5", status="paid_online")
    def result(response):
        saved = Payment.objects.get(pk=s.payment.pk)
        row = Refund.objects.get(payment=saved)
        assert (row.status, row.amount, row.external_refund_id) == ("succeeded", Decimal("25"), "re_g5")
        assert (saved.status, saved.amount) == ("paid_online", Decimal("100"))
        assert ports.calls[-1][0] == "refund" and ports.calls[-1][2]["amount"] == 2500
        assert response.data["refunds"][0]["id"] == row.pk
    url = reverse("payment-reconciliation-refund", kwargs={"makerspace_id": s.space.pk, "payment_id": s.payment.pk})
    # 481/494 staff path concealment; disabling NEW collections cannot strand a captured refund.
    cycle(world(s.space, s.client, url, "POST", {"amount": "25.00", "reason": "G5 online refund"},
        audit=("payment.refunded",), check=result, probes=[hidden(s.foreign)]), key)

"""Platform rail allowance gates new provider objects, with test credentials only."""
from decimal import Decimal

import pytest
from django.db import connection
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.payments.models import MakerspacePaymentSettings, Payment, PlatformStripeConnectSettings
from apps.payments.reconciliation import mark_offline
from tests.machines.test_intake_limits_cx7_p4b import member_client
from tests.makerspaces.test_daily_delivery_creator_races_cx7 import race
from tests.payments.money_subject_cx11b_p2 import subject
from tests.return_helpers import enable_online_rail, make_member, make_space, settlement_details

pytestmark = [pytest.mark.django_db, pytest.mark.area_payments_ledger, pytest.mark.area_payments]
KEYS = ["platform_payments_monthly_count", "platform_payments_monthly_amount"]


def setup(key, surface, settings, monkeypatch):
    settings.PLATFORM_DOMAIN_SUFFIX = ".managed.test"
    settings.INFRA_HOSTS = {"testserver"}
    settings.PUBLIC_APP_BASE_URL = "https://app.managed.test"
    settings.MANAGED_PLANS_ENABLED = False
    platform = PlatformStripeConnectSettings.load()
    platform.set_stripe_secret_key("sk_test_cx7_platform")
    platform.set_stripe_webhook_secret("whsec_test_cx7_platform")
    platform.stripe_publishable_key = "pk_test_cx7_platform"
    platform.stripe_connect_client_id = "ca_test_cx7_platform"
    platform.save()
    space = make_space("cx7-p4b-rail")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"payments", "bookings", "member_accounts"})
    space.save(update_fields=["enabled_modules"])
    enable_online_rail(space, "bookings")
    merchant = MakerspacePaymentSettings.objects.create(makerspace=space, connect_account_id="acct_testCx7",
        connect_status="active", connect_charges_enabled=True, connect_payouts_enabled=True)
    monkeypatch.setattr("apps.payments.services_checkout.refresh_connected_account", lambda row: merchant)
    monkeypatch.setattr("apps.payments.services_mobile.refresh_connected_account", lambda row: merchant)
    calls = []

    def checkout(source, **values):
        assert source.secret_key.startswith("sk_test_")
        calls.append(values["metadata"]["payment_id"])
        return {"id": "cs_test_" + calls[-1], "url": "https://checkout.stripe.test/" + calls[-1]}

    def intent(source, **values):
        assert source.secret_key.startswith("sk_test_")
        calls.append(values["metadata"]["payment_id"])
        return {"id": "pi_test_" + calls[-1], "client_secret": "pi_test_secret_" + calls[-1]}

    monkeypatch.setattr("apps.payments.stripe_client.create_checkout_session", checkout)
    monkeypatch.setattr("apps.payments.stripe_client.create_payment_intent", intent)
    rows, clients = [], []
    for index in range(2):
        kind, row, person = subject(space, "bookings")
        rows.append(Payment.objects.create(makerspace=space, member=person, created_by=person,
            subject_type=kind, subject_id=row.pk, amount=Decimal("10"), currency="usd", provider="stripe",
            stripe_provider="connect", stripe_connected_account_id="acct_testCx7"))
        clients.append(member_client(person, surface, settings, monkeypatch, space.pk, host="testserver"))
    space.resource_limit_overrides = {key: 10 if key.endswith("amount") else 1,
                                    "payments_monthly_count": 0, "payments_monthly_amount": 0}
    space.save(update_fields=["resource_limit_overrides"])
    return space, rows, clients, calls


def post(client, row, rail):
    return client.post(reverse("member-payment-mobile-intent" if rail == "native" else "member-payment-checkout",
        kwargs={"makerspace_id": row.makerspace_id, "payment_id": row.pk}), {}, format="json")


@pytest.mark.parametrize("key", KEYS)
@pytest.mark.parametrize("rail,surface", [("checkout", "browser"), ("checkout", "apple"),
    ("checkout", "android"), ("native", "apple"), ("native", "android")])
def test_rail_max_next_typed_refusal_keeps_debt_payable_offline(key, rail, surface, settings, monkeypatch):
    space, rows, clients, calls = setup(key, surface, settings, monkeypatch)
    assert post(clients[0], rows[0], rail).status_code == 200
    before = (list(Payment.objects.order_by("pk").values()), list(AuditLog.objects.order_by("pk").values()))
    refused = post(clients[1], rows[1], rail)
    assert (refused.status_code, refused.json()["code"]) == (409, "platform_rail_limit_reached")
    assert (list(Payment.objects.order_by("pk").values()), list(AuditLog.objects.order_by("pk").values())) == before
    assert calls == [str(rows[0].pk)]
    staff = make_member("cx7-p4b-offline-settler", space)
    mark_offline(rows[1], staff, settlement_details(reference="CX7-P4B"))
    rows[1].refresh_from_db()
    assert rows[1].status == "paid_offline"
    assert rows[1].manual_settlements.get().reference == "CX7-P4B"


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("key", KEYS)
@pytest.mark.parametrize("rail,surface", [("checkout", "browser"), ("native", "apple"), ("native", "android")])
def test_parallel_rail_starts_admit_only_the_charge_with_the_last_allowance(key, rail, surface, settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    _, rows, clients, calls = setup(key, surface, settings, monkeypatch)
    results = race(lambda index: post(clients[index], rows[index], rail))
    assert sorted(response.status_code for response in results) == [200, 409]
    assert [response.json()["code"] for response in results if response.status_code == 409] == ["platform_rail_limit_reached"]
    winner = next(index for index, response in enumerate(results) if response.status_code == 200)
    assert calls == [str(rows[winner].pk)]
    assert Payment.objects.filter(pk__in=[row.pk for row in rows], online_rail__isnull=False).count() == 1


@pytest.mark.parametrize("rail,surface", [("checkout", "browser"), ("native", "apple"), ("native", "android")])
@pytest.mark.parametrize("switch", ["payments", "payments.enabled", "payments.bookings"])
def test_rail_switch_off_preserves_debt_and_back_on_starts_at_capacity(rail, surface, switch, settings, monkeypatch):
    space, rows, clients, calls = setup("platform_payments_monthly_count", surface, settings, monkeypatch)
    field = "enabled_features" if "." in switch else "enabled_modules"
    saved = getattr(space, field)
    setattr(space, field, [value for value in saved if value != switch])
    space.save(update_fields=[field])
    before = list(Payment.objects.order_by("pk").values())
    refused = post(clients[0], rows[0], rail)
    assert (refused.status_code, refused.json()["code"]) == ((404, "module_disabled") if switch == "payments"
                                                          else (503, "payments_unavailable"))
    assert list(Payment.objects.order_by("pk").values()) == before
    assert calls == []
    setattr(space, field, saved)
    space.save(update_fields=[field])
    assert post(clients[0], rows[0], rail).status_code == 200
    assert len(calls) == 1

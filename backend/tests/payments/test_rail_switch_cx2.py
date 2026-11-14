"""Switching off the rail hides both minting routes and preserves the permanent debt."""
import pytest
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.payments.models import Payment
from tests.payments.account_helpers import make_payer
from tests.payments.test_mobile_payments import configured_payment, device_client
from tests.return_helpers import authenticated_client, make_space

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("native", [False, True])
def test_web_and_native_rail_off_refuse_without_touching_the_debt(native, monkeypatch):
    space = make_space("cx2-rail")
    owner = make_payer("cx2-rail-owner", space)
    payment = configured_payment(space, owner)
    calls = []
    if native:
        client = device_client(owner, space)
        name = "member-payment-mobile-intent"
        payload = {"vendor": "stripe", "payment_id": payment.pk,
                   "client_secret": "test_secret", "publishable_key": "pk_test"}
        def provider(*args, **kwargs):
            calls.append(payment.pk)
            return payload
        monkeypatch.setattr("apps.payments_rail.views_member_mobile.create_mobile_intent", provider)
    else:
        client = authenticated_client(owner)
        name = "member-payment-checkout"
        def provider(*args, **kwargs):
            calls.append(payment.pk)
            return "https://checkout.example.test/session"
        monkeypatch.setattr("apps.payments_rail.views_member_checkout.create_checkout_url", provider)
    url = reverse(name, args=[space.pk, payment.pk])
    response = client.post(url, {}, format="json")
    assert response.status_code == 200, response.data
    assert calls == [payment.pk]
    before = Payment.objects.filter(pk=payment.pk).values().get()
    original = space.enabled_modules
    space.enabled_modules = [key for key in original if key != "payments"]
    space.save(update_fields=["enabled_modules"])
    audit_count = AuditLog.objects.count()
    response = client.post(url, {}, format="json")
    assert (response.status_code, response.data["code"], response.data["module"]) == (404, "module_disabled", "payments")
    assert calls == [payment.pk]
    assert Payment.objects.filter(pk=payment.pk).values().get() == before
    assert AuditLog.objects.count() == audit_count
    space.enabled_modules = original
    space.save(update_fields=["enabled_modules"])
    assert Payment.objects.filter(pk=payment.pk).values().get() == before
    response = client.post(url, {}, format="json")
    assert response.status_code == 200, response.data
    assert calls == [payment.pk, payment.pk]


@pytest.mark.parametrize("enabled", [False, True])
def test_unrelated_member_cannot_distinguish_a_real_charge_from_a_missing_one(enabled):
    space = make_space("cx2-rail-hidden")
    owner = make_payer("cx2-rail-hidden-owner", space)
    payment = configured_payment(space, owner)
    stranger = make_payer("cx2-rail-stranger", make_space("cx2-rail-other"))
    if not enabled:
        space.enabled_modules = [key for key in space.enabled_modules if key != "payments"]
        space.save(update_fields=["enabled_modules"])
    client = authenticated_client(stranger)
    for payment_id in (payment.pk, 987654):
        response = client.post(reverse("member-payment-checkout", args=[space.pk, payment_id]), {}, format="json")
        assert (response.status_code, response.data["code"]) == (404, "not_found")

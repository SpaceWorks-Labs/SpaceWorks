"""Missing monthly boundaries: real usage, exact refusal and tenant isolation."""
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.managed_hosting import platform_limits as pl, space_quotas as sq
from apps.payments.models import Payment, PlatformStripeConnectSettings
from tests.limits_0120.test_payment_amount_boundaries_cx7 import _charge
from tests.payments.account_helpers import make_payer
from tests.payments.test_track3_booking_event_charging import bookable
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def independent_of_hosting(settings):
    settings.MANAGED_PLANS_ENABLED = False


@pytest.mark.parametrize("suffix", ["", ".space-works.tech"])
@pytest.mark.parametrize("key", ["events_monthly", "bookings_monthly", "payments_monthly_count"])
def test_monthly_count_last_slot_then_exact_refusal_with_real_rows(key, suffix, settings):
    settings.PLATFORM_DOMAIN_SUFFIX = suffix
    space = make_space("cx7-monthly-count")
    other = make_space("cx7-monthly-other")
    payer = make_payer("cx7-monthly-payer", space)
    other_payer = make_payer("cx7-monthly-other-payer", other)
    if key == "events_monthly":
        from apps.events.models import Event
        def create(target):
            start = timezone.now() + timedelta(days=1)
            return Event.objects.create(makerspace=target, title="Counted draft", starts_at=start,
                                        ends_at=start + timedelta(hours=1))
    elif key == "bookings_monthly":
        from apps.bookings.models import Booking
        def create(target):
            start = timezone.now() + timedelta(days=1)
            return Booking.objects.create(space=bookable(target, amount="0.00"),
                member=payer if target == space else other_payer, name="Borrower", email="borrower@example.com",
                starts_at=start, ends_at=start + timedelta(hours=1))
    else:
        def create(target):
            return _charge(target, payer if target == space else other_payer, "1.00")
    space.resource_limit_overrides = {key: 1}
    space.save(update_fields=["resource_limit_overrides"])
    create(other)
    assert sq.quota_used(space, key) == 0
    assert sq.check_space_quota(space, key) is None
    row = create(space)
    assert sq.quota_used(space, key) == 1
    with pytest.raises(sq.SpaceQuotaReached) as raised:
        sq.check_space_quota(space, key)
    assert raised.value.status_code == 409
    assert raised.value.code == sq.CODES[key]
    assert str(raised.value.detail["code"]) == sq.CODES[key]
    assert str(raised.value.detail["limit"]) == "1"
    assert type(row).objects.filter(pk=row.pk).exists()
    assert sq.quota_used(other, key) == 1


@pytest.mark.parametrize("key", ["platform_payments_monthly_count", "platform_payments_monthly_amount"])
def test_platform_rail_last_charge_stays_payable_and_next_has_exact_refusal(key, monkeypatch):
    from apps.payments import checkout_coordination as cc
    from apps.payments_rail.views_member_checkout import MemberPaymentCheckoutView
    from rest_framework.test import APIRequestFactory, force_authenticate
    space = make_space("cx7-platform-rail-boundary")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"payments"})
    space.save(update_fields=["enabled_modules"])
    payer = make_payer("cx7-platform-rail-payer", space)
    monkeypatch.setattr("apps.payments.availability.online_payments_enabled", lambda *_: True)
    monkeypatch.setattr("apps.payments.services.resolve_payment_source", lambda *_: SimpleNamespace(
        vendor="stripe", provider="connect", connected_account_id="acct_cx7", application_fee_bps=0))
    space.resource_limit_overrides = {key: 1 if key.endswith("count") else 10}
    space.save(update_fields=["resource_limit_overrides"])
    maximum = _charge(space, payer, "10.00")
    assert pl.rail_refusal(space, maximum) is None
    next_charge = _charge(space, payer, "0.01")
    expected = f"This space has used the {pl.LABELS[key]} allowed by the platform ({space.resource_limit_overrides[key]})."
    assert pl.rail_refusal(space, next_charge) == expected
    PlatformStripeConnectSettings.load()
    monkeypatch.setattr(cc, "source_for_payment", lambda *_: object())
    with pytest.raises(cc.PlatformRailLimitReached) as raised:
        cc._create_checkout_url_atomic(next_charge.pk)
    assert (raised.value.code, str(raised.value)) == ("platform_rail_limit_reached", expected)
    request = APIRequestFactory().post("/checkout", {}, format="json")
    force_authenticate(request, payer)
    response = MemberPaymentCheckoutView.as_view()(request, makerspace_id=space.pk, payment_id=next_charge.pk)
    assert response.status_code == 409
    assert response.data["code"] == "platform_rail_limit_reached"
    assert response.data["detail"] == expected
    assert Payment.objects.filter(makerspace=space, status="pending").count() == 2
    assert pl.rail_refusal(space, maximum) is None


@pytest.mark.parametrize("key", ["platform_email_monthly", "platform_sms_monthly",
                                  "platform_whatsapp_monthly", "platform_push_monthly"])
def test_platform_delivery_last_slot_next_refusal_and_failure_release(key):
    from apps.integrations.models import EmailLog
    from apps.integrations.models_contract import NotificationDelivery, NotificationEnvelope
    space = make_space("cx7-platform-delivery")
    space.resource_limit_overrides = {key: 1}
    space.save(update_fields=["resource_limit_overrides"])
    assert pl.platform_used(space, key) == 0
    assert pl.platform_refusal(space, key, adding=1) is None
    if key == "platform_email_monthly":
        row = EmailLog.objects.create(makerspace=space, to_email="recipient@example.com", subject="Counted",
                                      provider_source="platform", status="queued")
    else:
        envelope = NotificationEnvelope.objects.create(makerspace=space, feature="test", event="test",
                                                         dedup_key=f"cx7-{key}")
        row = NotificationDelivery.objects.create(makerspace=space, envelope=envelope, state="retrying",
            channel={"platform_sms_monthly": "sms", "platform_whatsapp_monthly": "whatsapp",
                     "platform_push_monthly": "native_push"}[key], provider_source="platform")
    assert pl.platform_used(space, key) == 1
    expected = f"This space has used the {pl.LABELS[key]} allowed by the platform (1)."
    assert pl.platform_refusal(space, key, adding=1) == expected
    assert pl.platform_refusal(space, key, adding=0) is None
    if key == "platform_email_monthly":
        EmailLog.objects.filter(pk=row.pk).update(status="failed")
    else:
        NotificationDelivery.objects.filter(pk=row.pk).update(state="failed", retryable=False)
    assert pl.platform_used(space, key) == 0
    assert pl.platform_refusal(space, key, adding=1) is None


def test_platform_wallet_last_slot_and_next_refusal_count_only_platform_passes():
    from apps.audit.models import AuditLog
    from apps.card_designs.models import WalletPass
    from apps.card_designs.wallet.credentials import auth_token, digest
    from apps.makerspaces import member_card_services
    from tests.l3_local.helpers import card_space, manager, member
    space = card_space("cx7-wallet-boundary")
    card = member_card_services.issue_card(manager(space), member(space)[1])
    key = "platform_wallet_monthly"
    space.resource_limit_overrides = {key: 1}
    space.save(update_fields=["resource_limit_overrides"])
    assert pl.platform_refusal(space, key) is None
    for source, platform in (("own", "apple"), ("platform", "google")):
        row = WalletPass.objects.create(makerspace=space, member_card=card, platform=platform, serial=source,
                                        auth_token_digest=digest(auth_token(source)))
        AuditLog.objects.create(action="wallet_pass.issued", makerspace=space,
                                meta={"pass_id": row.pk, "platform": platform, "source": source})
    assert pl.platform_used(space, key) == 1
    assert pl.platform_refusal(space, key, adding=0) is None
    assert pl.platform_refusal(space, key) == "This space has used the new wallet passes signed with the platform certificates this month allowed by the platform (1)."

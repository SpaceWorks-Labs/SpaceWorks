"""Money quotas compare exact currency amounts, including fractional remainders."""
from decimal import Decimal
from datetime import timedelta

import pytest

from apps.managed_hosting import platform_limits, space_quotas
from apps.payments.models import Payment
from apps.payments.services import create_payment
from apps.bookings.models import Booking
from django.utils import timezone
from tests.payments.account_helpers import make_payer
from tests.payments.test_track3_booking_event_charging import bookable
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db


def _charge(space, member, amount, currency="usd"):
    starts_at = timezone.now() + timedelta(hours=2)
    booking = Booking.objects.create(space=bookable(space, amount="0.00"), member=member,
                                    name=member.username, email="payer@example.com",
                                    starts_at=starts_at, ends_at=starts_at + timedelta(hours=1))
    return create_payment(makerspace=space, subject_type="booking", subject_id=booking.pk,
                          member=member, amount=Decimal(amount), currency=currency, created_by=member)


@pytest.mark.parametrize("currency, used, last, too_many", [
    ("usd", "9.99", "0.01", "0.02"),
    ("kwd", "9.99", "0.01", "0.02"),
])
def test_monthly_amount_accepts_the_last_cent_and_refuses_one_cent_more(settings, currency, used, last, too_many):
    settings.MANAGED_PLANS_ENABLED = False
    space = make_space("cx7-money-limit")
    payer = make_payer("cx7-money-payer", space)
    payment = _charge(space, payer, used, currency=currency)
    payment.refresh_from_db()
    assert payment.amount == Decimal(used)
    space.resource_limit_overrides = {"payments_monthly_amount": 10}
    space.save(update_fields=["resource_limit_overrides"])
    assert space_quotas.quota_used(space, "payments_monthly_amount", currency) == Decimal(used)
    assert space_quotas.require_payment_capacity(space, Decimal(last), currency) is None
    with pytest.raises(space_quotas.SpaceQuotaReached) as raised:
        space_quotas.require_payment_capacity(space, Decimal(too_many), currency)
    assert raised.value.status_code == 409
    assert raised.value.code == "payment_quota_reached"
    assert str(raised.value.detail["code"]) == "payment_quota_reached"
    final = _charge(space, payer, last, currency=currency)
    final.refresh_from_db()
    assert final.amount == Decimal(last)
    assert space_quotas.quota_used(space, "payments_monthly_amount", currency) == Decimal("10.00")
    with pytest.raises(space_quotas.SpaceQuotaReached) as full:
        space_quotas.require_payment_capacity(space, Decimal(last), currency)
    assert (full.value.status_code, str(full.value.detail["code"])) == (409, "payment_quota_reached")
    assert space_quotas.require_payment_capacity(space, Decimal("10"), "eur") is None
    assert Payment.objects.filter(makerspace=space).count() == 2


def test_amount_quota_never_prevents_recording_an_existing_debt(settings):
    settings.MANAGED_PLANS_ENABLED = False
    space = make_space("cx7-existing-debt")
    space.resource_limit_overrides = {"payments_monthly_amount": 0, "payments_monthly_count": 0}
    space.save(update_fields=["resource_limit_overrides"])
    payer = make_payer("cx7-debt-payer", space)
    payment = _charge(space, payer, "10.01")
    assert payment.amount == Decimal("10.01")
    assert payment.provider == "unclaimed"
    assert Payment.objects.filter(makerspace=space).count() == 1


def test_platform_counter_preserves_fractional_usage_and_currency(monkeypatch):
    space = make_space("cx7-platform-amount")
    payer = make_payer("cx7-platform-payer", space)
    # Stamp the actual creation path as Connect, without calling any external provider.
    from types import SimpleNamespace
    monkeypatch.setattr("apps.payments.availability.online_payments_enabled", lambda *_: True)
    monkeypatch.setattr("apps.payments.services.resolve_payment_source", lambda *_: SimpleNamespace(
        vendor="stripe", provider="connect", connected_account_id="acct_cx7", application_fee_bps=0))
    _charge(space, payer, "9.99")
    _charge(space, payer, "8.00", currency="eur")
    space.resource_limit_overrides = {"platform_payments_monthly_amount": 10}
    space.save(update_fields=["resource_limit_overrides"])
    assert platform_limits.platform_used(space, "platform_payments_monthly_amount", "usd") == Decimal("9.99")
    assert platform_limits.platform_used(space, "platform_payments_monthly_amount", "eur") == Decimal("8.00")
    assert platform_limits.platform_refusal(space, "platform_payments_monthly_amount",
                                            Decimal("0.01"), currency="usd") is None
    refusal = platform_limits.platform_refusal(space, "platform_payments_monthly_amount",
                                               Decimal("0.02"), currency="usd")
    assert refusal == "This space has used the money taken through the platform rail this month (per currency) allowed by the platform (10)."

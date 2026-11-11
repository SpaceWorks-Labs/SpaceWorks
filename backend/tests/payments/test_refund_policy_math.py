"""Refund policy arithmetic: bands, fee, cap, refunded-elsewhere and currency precision."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.payments.models import Payment, Refund
from apps.payments.refund_policy import assess, round_down
from tests.payments.refund_case_helpers import (
    charge, member, membership_charge, paid_event, policy, registration, space_with_currency,
)

pytestmark = pytest.mark.django_db


def setup(slug, *, starts_in=timedelta(days=3), amount="20.00", currency="usd"):
    space = space_with_currency(slug, currency)
    user = member(f"{slug}-m", space)
    reg = registration(paid_event(space, starts_in=starts_in, amount=amount), user)
    payment = charge(space, user, subject_id=reg.pk, amount=amount, currency=currency)
    return space, payment


@pytest.mark.parametrize("starts_in,expected,band", [
    (timedelta(days=3), Decimal("20.00"), "full"),
    (timedelta(hours=30), Decimal("10.00"), "partial"),
    (timedelta(hours=2), Decimal("0.00"), "none"),
])
def test_bands_pick_full_then_percent_then_nothing(starts_in, expected, band):
    space, payment = setup(f"policy-band-{band}", starts_in=starts_in)
    policy(space)
    due, snapshot = assess(payment, reason_code="registration_cancelled")
    assert due == expected and snapshot["band"] == band and snapshot["rule"] == "policy"


def test_fee_is_kept_floored_at_zero_and_only_in_the_space_currency():
    space, payment = setup("policy-fee", starts_in=timedelta(hours=30))
    policy(space, fee="3.00")
    assert assess(payment, reason_code="registration_cancelled")[0] == Decimal("7.00")
    policy_row = space.refund_policies.get()
    policy_row.cancellation_fee = Decimal("50.00")
    policy_row.save()
    assert assess(payment, reason_code="registration_cancelled")[0] == Decimal("0.00")
    from apps.events.models import EventRegistration
    event = EventRegistration.objects.get(pk=payment.subject_id).event
    guest = member("policy-fee-guest", space)
    other = charge(space, guest, subject_id=registration(event, guest).pk, currency="eur")
    due, snapshot = assess(other, reason_code="registration_cancelled")
    assert due == Decimal("10.00") and snapshot["fee_applied"] == "0.00"


def test_refunds_already_made_reduce_the_due_and_the_balance_caps_it():
    space, payment = setup("policy-refunded")
    policy(space)
    Refund.objects.create(payment=payment, amount=Decimal("15.00"), currency="usd", status="succeeded",
                          provider="manual", method="cash", refunded_at=timezone.now(), settled_at=timezone.now(),
                          created_by=payment.member)
    due, snapshot = assess(payment, reason_code="registration_cancelled")
    assert due == Decimal("5.00") and snapshot["already_refunded"] == "15.00"


def test_space_cancelled_event_is_owed_in_full_without_a_policy():
    _, payment = setup("policy-event-cancelled", starts_in=timedelta(minutes=5))
    due, snapshot = assess(payment, reason_code="event_cancelled")
    assert due == Decimal("20.00") and snapshot["rule"] == "event_cancelled_full"


def test_no_policy_or_no_area_owes_nothing():
    space, payment = setup("policy-none")
    due, snapshot = assess(payment, reason_code="registration_cancelled")
    assert due == Decimal("0.00") and snapshot["rule"] == "no_policy"
    membership = membership_charge(space, payment.member)
    assert assess(membership, reason_code="registration_cancelled")[1]["rule"] == "no_reference_time"


@pytest.mark.parametrize("currency,amount,expected", [
    ("jpy", "1001.00", Decimal("500")),     # zero-decimal: whole yen, rounded down
    ("bhd", "10.01", Decimal("5.00")),      # three-decimal, stored at two: min(3, 2)
    ("usd", "10.01", Decimal("5.00")),
])
def test_partial_amounts_round_down_to_the_stored_precision(currency, amount, expected):
    space, payment = setup(f"policy-round-{currency}", starts_in=timedelta(hours=30), amount=amount,
                           currency=currency)
    policy(space)
    due, _ = assess(payment, reason_code="registration_cancelled")
    assert due == expected
    assert round_down(Decimal("1.999"), "bhd") == Decimal("1.99")
    assert round_down(Decimal("9.99"), "jpy") == Decimal("9")

"""Decision 260: a refund whose create call had an unknown outcome is found and settled by the poll."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.payments import gateway_poll
from apps.payments.models import Payment, Refund
from tests.payments.test_razorpay_refund_sync import _paid_razorpay_deposit

pytestmark = pytest.mark.django_db


def _unbound(slug, age):
    space, staff, payment = _paid_razorpay_deposit(slug, external_id=f"pay_{slug}")
    refund = Refund.objects.create(payment=payment, amount=Decimal("100.00"), currency="inr",
                                   provider="razorpay", created_by=staff)
    Refund.objects.filter(pk=refund.pk).update(created_at=timezone.now() - age)
    return space, payment, Refund.objects.get(pk=refund.pk)


def test_old_unbound_refund_is_polled_but_a_fresh_one_is_not():
    space, _payment, refund = _unbound("g2-poll-old", timedelta(minutes=30))
    assert refund in list(gateway_poll._pending_refunds(space, timezone.now()))
    space2, _p2, fresh = _unbound("g2-poll-new", timedelta(seconds=30))
    assert fresh not in list(gateway_poll._pending_refunds(space2, timezone.now()))


def test_found_refund_is_bound_and_settled_idempotently(monkeypatch):
    _space, payment, refund = _unbound("g2-poll-found", timedelta(minutes=30))
    monkeypatch.setattr("apps.payments.resolution.source_for_payment", lambda _p: object())
    monkeypatch.setattr("apps.payments_rail.provider_poll.find_refund",
                        lambda _r, _s: ("rfnd_unknown_1", "succeeded"))
    now = timezone.now()
    assert gateway_poll._poll_refund(refund, now) is True
    refund.refresh_from_db()
    assert refund.status == Refund.Status.SUCCEEDED and refund.external_refund_id == "rfnd_unknown_1"
    assert gateway_poll._poll_refund(refund, now) is False or refund.status == Refund.Status.SUCCEEDED
    assert Refund.objects.filter(payment=payment, status=Refund.Status.SUCCEEDED).count() == 1


def test_not_found_keeps_the_refund_pending_and_reserved(monkeypatch):
    _space, payment, refund = _unbound("g2-poll-missing", timedelta(minutes=30))
    monkeypatch.setattr("apps.payments.resolution.source_for_payment", lambda _p: object())
    monkeypatch.setattr("apps.payments_rail.provider_poll.find_refund", lambda _r, _s: None)
    assert gateway_poll._poll_refund(refund, timezone.now()) is False
    refund.refresh_from_db()
    assert refund.status == Refund.Status.PENDING
    assert Refund.counted_total(Payment.objects.get(pk=payment.pk)) == Decimal("100.00")

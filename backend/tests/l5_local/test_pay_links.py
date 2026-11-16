"""X19 pay links and X18 gateway polling: account-less payment, read-only polling, never a refund."""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.payments.gateway_poll import _poll_attempt, _poll_refund
from apps.payments.models import Payment, PaymentClaim, PaymentPayLink, Refund
from apps.payments_rail.provider_poll import PolledCapture
from tests.l5_local.helpers import accountless, client, dues, setup, switch

pytestmark = pytest.mark.django_db


def _accountless(space, manager, payer):
    return accountless(space, manager)


def _create(space, manager, payment):
    return client(manager).post(f"/api/v1/admin/makerspace/{space.pk}/payments/{payment.pk}/pay-link", {},
                                format="json")


def test_pay_links_are_off_by_default():
    space, manager, payer = setup("paylink-off")
    assert _create(space, manager, _accountless(space, manager, payer)).status_code == 404


def test_link_shows_only_what_is_owed_and_takes_a_claim():
    space, manager, payer = setup("paylink-on", "billing.pay_links", "billing.offline_claims")
    payment = _accountless(space, manager, payer)
    created = _create(space, manager, payment)
    assert created.status_code == 201
    token = created.json()["url"].rsplit("/", 1)[1]
    assert not PaymentPayLink.objects.filter(token_digest=token).exists()  # only the digest is stored
    public = APIClient()
    shown = public.get(f"/api/v1/public/pay/{token}").json()
    assert shown["amount"] == "75.00" and shown["label"] == "Workshop fee"
    assert payer.username not in str(shown) and payer.email not in str(shown)
    claimed = public.post(f"/api/v1/public/pay/{token}/claim", {"reference": "UTR555555555",
                                                                "paid_on": timezone.localdate().isoformat()},
                          format="json")
    assert claimed.status_code == 201 and PaymentClaim.objects.get().claimant is None


def test_links_refuse_charges_with_an_account_and_expired_links_are_dead():
    space, manager, payer = setup("paylink-refuse", "billing.pay_links")
    refused = _create(space, manager, dues(space, payer))
    assert refused.status_code == 409 and refused.json()["code"] == "pay_link_has_account"
    payment = _accountless(space, manager, payer)
    token = _create(space, manager, payment).json()["url"].rsplit("/", 1)[1]
    PaymentPayLink.objects.filter(payment=payment).update(expires_at=timezone.now() - timedelta(minutes=1))
    assert APIClient().get(f"/api/v1/public/pay/{token}").status_code == 404
    switch(space, "billing.pay_links", on=False)


def test_poll_settles_a_capture_like_its_webhook_and_closes_week_old_attempts():
    space, _manager, payer = setup("poll", "billing.capture_flags")
    payment = dues(space, payer, "10.00", provider=Payment.Provider.STRIPE)
    Payment.objects.filter(pk=payment.pk).update(stripe_checkout_session_id="cs_poll")
    payment.refresh_from_db()
    with patch("apps.payments.resolution.source_for_payment", return_value=object()), \
            patch("apps.payments_rail.provider_poll.poll_checkout",
                  return_value=PolledCapture(True, "pi_poll", 1000, "inr", "Visa ••4242")):
        assert _poll_attempt(payment, timezone.now())
    payment.refresh_from_db()
    assert payment.status == Payment.Status.PAID_ONLINE and payment.method_label == "Visa ••4242"

    stale = dues(space, payer, "11.00", provider=Payment.Provider.STRIPE)
    Payment.objects.filter(pk=stale.pk).update(stripe_checkout_session_id="cs_stale")
    stale.refresh_from_db()
    with patch("apps.payments.resolution.source_for_payment", return_value=object()), \
            patch("apps.payments_rail.provider_poll.poll_checkout", return_value=PolledCapture(False)), \
            patch("apps.payments.reconciliation_rail._expire_checkout_best_effort"):
        assert _poll_attempt(stale, timezone.now() + timedelta(days=8))
    stale.refresh_from_db()
    assert stale.status == Payment.Status.PENDING and stale.stripe_checkout_session_expired_at is not None


def test_polling_a_pending_refund_never_creates_one():
    space, manager, payer = setup("poll-refund")
    payment = dues(space, payer, "10.00", provider=Payment.Provider.STRIPE)
    Payment.objects.filter(pk=payment.pk).update(status=Payment.Status.PAID_ONLINE)
    refund = Refund.objects.create(payment=payment, amount=Decimal("10.00"), currency="inr", provider="stripe",
                                   external_refund_id="re_1", created_by=manager)
    Refund.objects.filter(pk=refund.pk).update(created_at=timezone.now() - timedelta(days=2))
    refund.refresh_from_db()
    with patch("apps.payments.resolution.source_for_payment", return_value=object()), \
            patch("apps.payments_rail.provider_poll.poll_refund", return_value="pending"):
        assert not _poll_refund(refund, timezone.now())
    assert Refund.objects.count() == 1

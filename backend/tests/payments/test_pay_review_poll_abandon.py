"""PAY-REVIEW 0.12.0: the gateway poll never forgets a hosted page that can still take money.

Abandoning a week-old attempt cleared the page's ids whether or not the provider had closed
it. A Razorpay link whose cancel failed stayed payable, and a Stripe session whose SEPA/ACH
debit was still processing (they can outlast a week) completed later -- in both cases the
webhook could no longer find the charge, so collected money left the debt PENDING.
"""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.payments.gateway_poll import _poll_attempt
from apps.payments.models import Payment
from apps.payments.providers.base import PaymentsUnavailable
from apps.payments.providers.razorpay import RazorpayProvider, RazorpayRequestError
from apps.payments.services_webhooks import apply_webhook_event
from apps.payments_rail.provider_poll import PolledCapture
from tests.payments.recon_f_helpers import pending_charge
from tests.payments.test_models import configured_settings
from tests.payments.test_razorpay_provider import configure_razorpay, paid_body, sign

pytestmark = pytest.mark.django_db
LATER = timedelta(days=8)


def _razorpay_link(slug):
    space, _staff, payment = pending_charge(slug, provider="razorpay", external_order_id=f"plink_{slug}",
                                            checkout_url="https://rzp.io/i/keep", online_rail="checkout")
    configure_razorpay(space)
    return space, payment


def _unreachable(self, source, method, path, body=None, *, idempotency_key=None):
    raise PaymentsUnavailable("Razorpay could not be reached.")


def test_a_link_whose_cancel_failed_is_kept_and_a_late_payment_still_settles():
    space, payment = _razorpay_link("prv-rzp-keep")
    with patch.object(RazorpayProvider, "_request", _unreachable), \
            patch("apps.payments_rail.provider_poll.poll_checkout", return_value=PolledCapture(False)):
        assert not _poll_attempt(payment, timezone.now() + LATER)
    payment.refresh_from_db()
    assert payment.external_order_id == "plink_prv-rzp-keep"
    assert payment.stripe_checkout_session_expired_at is None  # polled (and retried) again

    body = paid_body(link_id="plink_prv-rzp-keep", payment_id="pay_prv_late", payment_pk=payment.pk)
    response = APIClient().post(reverse("razorpay-webhook", args=[space.public_code]), data=body,
                                content_type="application/json", HTTP_X_RAZORPAY_SIGNATURE=sign(body),
                                HTTP_X_RAZORPAY_EVENT_ID="evt_prv_late")
    assert response.status_code == 200
    payment.refresh_from_db()
    assert payment.status == Payment.Status.PAID_ONLINE and payment.external_payment_id == "pay_prv_late"


def test_a_link_razorpay_reports_closed_is_forgotten():
    _space, payment = _razorpay_link("prv-rzp-closed")

    def refused_but_expired(self, source, method, path, body=None, *, idempotency_key=None):
        if method == "POST":
            raise RazorpayRequestError(400, "BAD_REQUEST_ERROR", "link already expired")
        return {"id": payment.external_order_id, "status": "expired"}

    with patch.object(RazorpayProvider, "_request", refused_but_expired), \
            patch("apps.payments_rail.provider_poll.poll_checkout", return_value=PolledCapture(False)):
        assert _poll_attempt(payment, timezone.now() + LATER)
    payment.refresh_from_db()
    assert payment.status == Payment.Status.PENDING
    assert payment.external_order_id is None and payment.checkout_url == ""
    assert payment.stripe_checkout_session_expired_at is not None


def _stripe_session(slug):
    space, _staff, payment = pending_charge(slug, provider="stripe", stripe_checkout_session_id=f"cs_{slug}",
                                            external_order_id=f"cs_{slug}", online_rail="checkout",
                                            checkout_url="https://checkout.stripe.test/s")
    configured_settings(space)
    return space, payment


def test_a_processing_debit_keeps_its_intent_so_a_late_success_settles():
    space, payment = _stripe_session("prv-sepa")
    with patch("apps.payments_rail.provider_poll.poll_checkout",
               return_value=PolledCapture(False, "pi_prv_sepa")), \
            patch("apps.payments.stripe_client.expire_checkout_session", return_value=False):
        assert not _poll_attempt(payment, timezone.now() + LATER)
    payment.refresh_from_db()
    assert payment.stripe_checkout_session_id == "cs_prv-sepa"
    assert payment.stripe_checkout_session_expired_at is None
    assert payment.stripe_payment_intent_id == "pi_prv_sepa"
    from apps.payments.services_checkout import create_checkout_url
    with patch("apps.payments.stripe_client.create_checkout_session") as create:
        assert create_checkout_url(payment.pk) == "https://checkout.stripe.test/s"
    create.assert_not_called()  # no second debit can replace this intent before its late success

    apply_webhook_event(space, {
        "id": "evt_prv_sepa", "type": "checkout.session.async_payment_succeeded",
        "data": {"object": {"id": "cs_prv-sepa", "payment_intent": "pi_prv_sepa",
                            "amount_total": 1000, "currency": "usd"}}})
    payment.refresh_from_db()
    assert payment.status == Payment.Status.PAID_ONLINE


def test_an_open_session_stripe_did_not_confirm_closed_is_retried_not_forgotten():
    _space, payment = _stripe_session("prv-open")
    with patch("apps.payments_rail.provider_poll.poll_checkout", return_value=PolledCapture(False)), \
            patch("apps.payments.stripe_client.expire_checkout_session", return_value=False):
        assert not _poll_attempt(payment, timezone.now() + LATER)
    payment.refresh_from_db()
    assert payment.stripe_checkout_session_id == "cs_prv-open"
    assert payment.stripe_checkout_session_expired_at is None

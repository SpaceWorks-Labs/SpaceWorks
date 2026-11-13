"""Repeated Stripe event identity is consumed once and cannot be burned by a foreign tenant."""
import pytest

from apps.audit.models import AuditLog
from apps.payments.models import Payment, ProcessedStripeEvent
from apps.payments.services import apply_webhook_event
from tests.payments.test_stripe_webhook_order_mod3 import _paid_event, _setup

pytestmark = pytest.mark.django_db


def test_the_same_stripe_event_id_settles_and_audits_exactly_once():
    space, payment = _setup("cx4-stripe-replay")
    Payment.objects.filter(pk=payment.pk).update(stripe_checkout_session_id="cs_cx4")
    event = _paid_event("evt_cx4", session="cs_cx4", intent="pi_cx4")
    result = apply_webhook_event(space, event)
    assert result.status == Payment.Status.PAID_ONLINE
    first = list(AuditLog.objects.filter(makerspace=space, target_type="payments.payment", target_id=str(payment.pk))
                 .order_by("pk").values_list("pk", "action", "meta"))
    assert [action for _, action, _ in first].count("payment.paid_online") == 1
    apply_webhook_event(space, event)
    payment.refresh_from_db()
    assert (payment.status, payment.stripe_payment_intent_id) == (Payment.Status.PAID_ONLINE, "pi_cx4")
    assert ProcessedStripeEvent.objects.filter(makerspace=space, stripe_event_id="evt_cx4").count() == 1
    assert list(AuditLog.objects.filter(makerspace=space, target_type="payments.payment", target_id=str(payment.pk))
                .order_by("pk").values_list("pk", "action", "meta")) == first


def test_a_foreign_tenant_cannot_burn_the_event_that_the_correct_tenant_will_replay():
    owner, payment = _setup("cx4-stripe-owner")
    foreign, other_payment = _setup("cx4-stripe-foreign")
    Payment.objects.filter(pk=payment.pk).update(stripe_checkout_session_id="cs_cx4_owner")
    event = _paid_event("evt_cx4_scope", session="cs_cx4_owner", intent="pi_cx4_owner")
    assert apply_webhook_event(foreign, event) is None
    assert ProcessedStripeEvent.objects.filter(stripe_event_id="evt_cx4_scope").count() == 0
    assert apply_webhook_event(owner, event).status == Payment.Status.PAID_ONLINE
    other_payment.refresh_from_db()
    assert other_payment.status == Payment.Status.PENDING
    assert AuditLog.objects.filter(makerspace=foreign, action="payment.paid_online").count() == 0
    assert ProcessedStripeEvent.objects.filter(makerspace=owner, stripe_event_id="evt_cx4_scope").count() == 1

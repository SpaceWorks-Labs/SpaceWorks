"""MOD-3 flow audit: Stripe webhook delivery order and duplication, one exact assertion each.

The ledger must settle a charge exactly once however Stripe orders, repeats or mis-scopes events.
"""
import pytest

from apps.audit.models import AuditLog
from apps.payments.models import Payment, ProcessedStripeEvent
from apps.payments.services import apply_webhook_event
from tests.payments.test_machine_payments import payment_for, service_request
from tests.payments.test_models import configured_settings
from tests.return_helpers import make_member, make_space

pytestmark = pytest.mark.django_db


def _paid_event(event_id, session="cs_m3", intent="pi_m3"):
    return {"id": event_id, "type": "checkout.session.completed",
            "data": {"object": {"id": session, "payment_status": "paid", "payment_intent": intent, "amount_total": 500, "currency": "usd"}}}


def _setup(slug):
    space = make_space(slug)
    space.enabled_features = ["payments.enabled", "payments.machines", "charges.enabled", "charges.machines"]
    space.save(update_fields=["enabled_features", "updated_at"])
    configured_settings(space)
    actor = make_member(f"{slug}-user", space)
    payment = payment_for(service_request(space, actor), actor)
    return space, payment


def test_an_event_that_arrives_before_the_checkout_ids_are_stored_is_not_burned():
    space, payment = _setup("m3-stripe-early")
    event = _paid_event("evt_m3_early")
    assert apply_webhook_event(space, event) is None  # no payment carries cs_m3 yet
    assert not ProcessedStripeEvent.objects.filter(makerspace=space, stripe_event_id="evt_m3_early").exists()
    Payment.objects.filter(pk=payment.pk).update(stripe_checkout_session_id="cs_m3")
    settled = apply_webhook_event(space, event)  # Stripe retries the same event id
    assert settled is not None and settled.status == Payment.Status.PAID_ONLINE
    assert ProcessedStripeEvent.objects.filter(makerspace=space, stripe_event_id="evt_m3_early").count() == 1


def test_a_failure_event_after_success_never_unsettles_the_charge():
    space, payment = _setup("m3-stripe-late-fail")
    Payment.objects.filter(pk=payment.pk).update(stripe_checkout_session_id="cs_m3")
    assert apply_webhook_event(space, _paid_event("evt_m3_ok")).status == Payment.Status.PAID_ONLINE
    late_failure = {"id": "evt_m3_fail", "type": "checkout.session.async_payment_failed", "data": {"object": {"id": "cs_m3"}}}
    apply_webhook_event(space, late_failure)
    payment.refresh_from_db()
    assert payment.status == Payment.Status.PAID_ONLINE
    assert payment.stripe_payment_intent_id == "pi_m3"


def test_a_second_paid_event_with_a_new_id_is_flagged_once_and_never_settles_twice():
    space, payment = _setup("m3-stripe-double")
    Payment.objects.filter(pk=payment.pk).update(stripe_checkout_session_id="cs_m3")
    assert apply_webhook_event(space, _paid_event("evt_m3_a")).status == Payment.Status.PAID_ONLINE
    apply_webhook_event(space, _paid_event("evt_m3_b"))  # different id, same capture
    apply_webhook_event(space, _paid_event("evt_m3_b"))  # and that one repeated
    payment.refresh_from_db()
    assert payment.status == Payment.Status.PAID_ONLINE
    assert AuditLog.objects.filter(makerspace=space, action="payment.double_paid_refund_required", target_id=str(payment.pk)).count() == 1


def test_the_same_event_id_is_processed_independently_per_makerspace():
    one, payment_one = _setup("m3-stripe-tenant-a")
    two, payment_two = _setup("m3-stripe-tenant-b")
    Payment.objects.filter(pk=payment_one.pk).update(stripe_checkout_session_id="cs_m3")
    Payment.objects.filter(pk=payment_two.pk).update(stripe_checkout_session_id="cs_m3")
    event = _paid_event("evt_shared_id")
    assert apply_webhook_event(one, event).status == Payment.Status.PAID_ONLINE
    assert apply_webhook_event(two, event).status == Payment.Status.PAID_ONLINE  # not swallowed as a duplicate
    payment_one.refresh_from_db(); payment_two.refresh_from_db()
    assert (payment_one.status, payment_two.status) == (Payment.Status.PAID_ONLINE, Payment.Status.PAID_ONLINE)
    assert ProcessedStripeEvent.objects.filter(stripe_event_id="evt_shared_id").count() == 2


def test_an_event_for_another_makerspaces_checkout_session_settles_nothing_here():
    one, payment_one = _setup("m3-stripe-scope-a")
    two, _payment_two = _setup("m3-stripe-scope-b")
    Payment.objects.filter(pk=payment_one.pk).update(stripe_checkout_session_id="cs_only_a")
    assert apply_webhook_event(two, _paid_event("evt_scope", session="cs_only_a")) is None
    payment_one.refresh_from_db()
    assert payment_one.status == Payment.Status.PENDING
    assert not ProcessedStripeEvent.objects.filter(stripe_event_id="evt_scope").exists()


def test_a_completed_session_that_is_not_paid_yet_settles_nothing_and_records_nothing():
    space, payment = _setup("m3-stripe-unpaid")
    Payment.objects.filter(pk=payment.pk).update(stripe_checkout_session_id="cs_m3")
    event = _paid_event("evt_m3_unpaid")
    event["data"]["object"]["payment_status"] = "unpaid"
    assert apply_webhook_event(space, event) is None
    payment.refresh_from_db()
    assert payment.status == Payment.Status.PENDING
    assert not ProcessedStripeEvent.objects.filter(makerspace=space).exists()

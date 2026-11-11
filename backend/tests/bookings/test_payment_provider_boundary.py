"""Provider outages cannot undo valid local debt or booking cancellation."""

from tests.account_split.sweep_g2_helpers import ledger_booking as build_ledger_booking

from unittest.mock import Mock

import pytest

from apps.audit.models import AuditLog
from apps.bookings import service_payments, services_bookings
from apps.bookings.models import Booking
from apps.payments import reconciliation
from apps.payments.models import Payment
from apps.payments.services import apply_webhook_event
from tests.bookings.payment_ledger_helpers import create_booking
from tests.payments.test_models import configured_settings
from tests.return_helpers import settlement_details

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("failure", ["readiness", "scheduling", "checkout"])
@pytest.mark.django_db(transaction=True)
def test_optional_checkout_failure_preserves_real_committed_confirmation(
    ledger_booking, monkeypatch, failure,
):
    _, space, member, _ = ledger_booking
    unavailable = Mock(side_effect=RuntimeError("provider unavailable"))
    monkeypatch.setattr(service_payments, "online_payments_enabled", lambda *_: True)
    target = {
        "readiness": "online_payments_enabled",
        "scheduling": "_schedule_checkout",
        "checkout": "create_checkout",
    }[failure]
    monkeypatch.setattr(service_payments, target, unavailable)

    booking = create_booking(space, member)

    unavailable.assert_called_once()
    booking.refresh_from_db()
    assert booking.status == Booking.Status.CONFIRMED
    payment = Payment.objects.get(subject_id=booking.pk)
    assert payment.status == Payment.Status.PENDING
    assert AuditLog.objects.filter(action="booking.created", target_id=str(booking.pk)).exists()
    assert AuditLog.objects.filter(action="payment.created", target_id=str(payment.pk)).exists()


@pytest.mark.parametrize("member_cancel", [False, True])
@pytest.mark.parametrize("rail", ["hosted", "native"])
@pytest.mark.django_db(transaction=True)
def test_provider_close_failure_preserves_committed_cancellation(
    ledger_booking, monkeypatch, member_cancel, rail,
):
    makerspace, space, member, manager = ledger_booking
    configured_settings(makerspace)
    booking = create_booking(space, member)
    before_sequence = booking.calendar_sequence
    payment = Payment.objects.get(subject_id=booking.pk)
    if rail == "hosted":
        Payment.objects.filter(pk=payment.pk).update(
            online_rail=Payment.OnlineRail.CHECKOUT,
            stripe_checkout_session_id="cs_bk0",
        )
        operation = "expire_checkout_session"
    else:
        Payment.objects.filter(pk=payment.pk).update(
            online_rail=Payment.OnlineRail.NATIVE_PAYMENT_INTENT,
            stripe_payment_intent_id="pi_bk0",
        )
        operation = "cancel_payment_intent"
    unavailable = Mock(side_effect=RuntimeError("provider unavailable"))
    monkeypatch.setattr(f"apps.payments.reconciliation_rail.stripe_client.{operation}", unavailable)

    services_bookings.cancel_booking(
        booking, actor=member if member_cancel else manager, member_cancel=member_cancel,
    )

    unavailable.assert_called_once()
    booking.refresh_from_db()
    payment.refresh_from_db()
    assert booking.status == Booking.Status.CANCELLED
    assert booking.calendar_sequence == before_sequence + 1
    assert payment.status == Payment.Status.CANCELED
    assert payment.stripe_checkout_session_expired_at is None
    assert AuditLog.objects.filter(action="booking.cancelled", target_id=str(booking.pk)).exists()
    assert AuditLog.objects.filter(action="payment.canceled", target_id=str(payment.pk)).exists()


@pytest.mark.parametrize("state", ["no_charge", "pending_booking", "canceled", "waived", "paid_offline", "paid_online"])
def test_cancellation_preserves_absent_or_terminal_debt(
    ledger_booking, monkeypatch, state,
):
    makerspace, space, member, manager = ledger_booking
    if state == "no_charge":
        space.payment_amount = 0
        space.save(update_fields=["payment_amount"])
    if state == "pending_booking":
        space.approval_mode = "approve"
        space.save(update_fields=["approval_mode"])
    if state == "paid_online":
        configured_settings(makerspace)
    booking = create_booking(space, member)
    payment = Payment.objects.filter(subject_id=booking.pk).first()
    if state == "canceled":
        reconciliation.cancel_pending(
            makerspace=makerspace, subject_type=Payment.SubjectType.BOOKING,
            subject_id=booking.pk, actor=manager,
        )
    elif state == "waived":
        reconciliation.waive(payment, manager)
    elif state == "paid_offline":
        reconciliation.mark_offline(payment, manager, settlement=settlement_details())
    elif state == "paid_online":
        Payment.objects.filter(pk=payment.pk).update(
            online_rail=Payment.OnlineRail.NATIVE_PAYMENT_INTENT,
            stripe_payment_intent_id="pi_bk0_settled",
        )
        apply_webhook_event(makerspace, {
            "id": "evt_bk0_settled", "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_bk0_settled"}},
        })
    before_payments = list(Payment.objects.values())
    before_cancel_audits = AuditLog.objects.filter(action="payment.canceled").count()
    expiry = Mock(side_effect=AssertionError("terminal or absent debt must not call provider"))
    monkeypatch.setattr(reconciliation, "_expire_checkout_best_effort", expiry)

    services_bookings.cancel_booking(booking, actor=manager)

    booking.refresh_from_db()
    assert booking.status == Booking.Status.CANCELLED
    assert list(Payment.objects.values()) == before_payments
    assert AuditLog.objects.filter(action="payment.canceled").count() == before_cancel_audits
    expiry.assert_not_called()
    if state == "paid_online":
        assert Payment.objects.get(pk=payment.pk).status == Payment.Status.PAID_ONLINE


def test_cancel_charge_lookup_is_scoped_to_booking_tenant_and_subject(ledger_booking):
    from tests.bookings.payment_ledger_helpers import bookable, member_with_phone
    from tests.return_helpers import make_space

    _, space, member, manager = ledger_booking
    own = create_booking(space, member)
    foreign_space = make_space("bk0-foreign")
    foreign_space.enabled_features = ["charges.enabled", "charges.bookings"]
    foreign_space.save(update_fields=["enabled_features"])
    foreign_member = member_with_phone("bk0-foreign-member", foreign_space)
    foreign = create_booking(bookable(foreign_space), foreign_member)
    unrelated = Payment.objects.get(subject_id=foreign.pk)
    before = Payment.objects.filter(pk=unrelated.pk).values().get()

    services_bookings.cancel_booking(own, actor=manager)

    assert Payment.objects.get(subject_id=own.pk).status == Payment.Status.CANCELED
    assert Payment.objects.filter(pk=unrelated.pk).values().get() == before
    foreign.refresh_from_db()
    assert foreign.status == Booking.Status.CONFIRMED


def test_foreign_member_cannot_cancel_or_change_debt(ledger_booking):
    from apps.bookings.exceptions import BookingInvalidTransition
    from tests.bookings.payment_ledger_helpers import ledger_state, member_with_phone
    from tests.return_helpers import make_space

    _, space, member, _ = ledger_booking
    booking = create_booking(space, member)
    foreign_member = member_with_phone("bk0-outsider", make_space("bk0-outsider"))
    before = ledger_state()

    with pytest.raises(BookingInvalidTransition, match="Only the booking member"):
        services_bookings.cancel_booking(booking, actor=foreign_member, member_cancel=True)

    assert ledger_state() == before


def test_disabling_tracking_does_not_prevent_cancellation_of_existing_debt(ledger_booking):
    makerspace, space, member, manager = ledger_booking
    booking = create_booking(space, member)
    makerspace.enabled_features = []
    makerspace.save(update_fields=["enabled_features"])

    services_bookings.cancel_booking(booking, actor=manager)

    booking.refresh_from_db()
    assert booking.status == Booking.Status.CANCELLED
    assert Payment.objects.get(subject_id=booking.pk).status == Payment.Status.CANCELED


@pytest.fixture
def ledger_booking():
    return build_ledger_booking()

"""Cancellation hooks: paid charges get a refund case, pending ones are voided, nothing pays out."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.bookings import services as booking_services
from apps.bookings.models import Booking
from apps.events import services as event_services
from apps.events.models import EventRegistration
from apps.payments.models import Payment, Refund, RefundCase
from apps.payments.refund_case_sweeper import rebuild_missed_refund_cases
from apps.payments.services_refund_cases import open_due_case, request_refund
from tests.payments.refund_case_helpers import (
    booking, charge, deposit, member, paid_event, policy, registration, space_with_currency,
)
from tests.return_helpers import make_member

pytestmark = pytest.mark.django_db


def test_space_cancelled_event_opens_a_full_due_case_and_voids_pending(django_capture_on_commit_callbacks):
    space = space_with_currency("hook-event-cancel")
    manager = make_member("hook-event-cancel-staff", space)
    event = paid_event(space)
    paid_user, pending_user = member("hook-paid", space), member("hook-pending", space)
    paid = charge(space, paid_user, subject_id=registration(event, paid_user).pk)
    pending = charge(space, pending_user, subject_id=registration(event, pending_user).pk, status="pending")
    with django_capture_on_commit_callbacks(execute=True):
        event_services.cancel(event, actor=manager)
    case = RefundCase.objects.get(payment=paid)
    assert (case.kind, case.status, case.reason_code, case.due_amount) == ("due", "open", "event_cancelled",
                                                                           Decimal("20.00"))
    assert Payment.objects.get(pk=pending.pk).status == "canceled"
    assert not RefundCase.objects.filter(payment=pending).exists()
    assert not Refund.objects.exists()  # an entitlement, never money
    assert Payment.objects.get(pk=paid.pk).status == "paid_offline"
    assert AuditLog.objects.filter(action="payment.refund_case_opened", meta__case_id=case.pk).exists()


def test_member_cancel_follows_the_policy_and_zero_due_opens_nothing(django_capture_on_commit_callbacks):
    space = space_with_currency("hook-member-cancel")
    policy(space, full=7 * 24 * 60, partial=24 * 60, percent=25)
    early, late = member("hook-early", space), member("hook-late", space)
    soon = paid_event(space, starts_in=timedelta(hours=3))
    later = paid_event(space, starts_in=timedelta(days=2))
    late_reg, early_reg = registration(soon, late), registration(later, early)
    charge(space, late, subject_id=late_reg.pk)
    early_payment = charge(space, early, subject_id=early_reg.pk)
    # The refund-case hook runs after the registration commit (events programme write boundary).
    with django_capture_on_commit_callbacks(execute=True):
        event_services.cancel_registration(early_reg, actor=early, member_cancel=True)
        event_services.cancel_registration(late_reg, actor=late, member_cancel=True)
    case = RefundCase.objects.get()
    assert case.payment == early_payment and case.due_amount == Decimal("5.00")
    assert case.reason_code == "registration_cancelled" and case.policy_snapshot["band"] == "partial"


def test_registration_cancel_survives_a_hook_failure_and_the_sweep_rebuilds(monkeypatch):
    space = space_with_currency("hook-sweep")
    policy(space, full=0, partial=0, percent=0)
    user = member("hook-sweep-m", space)
    reg = registration(paid_event(space), user)
    payment = charge(space, user, subject_id=reg.pk)
    monkeypatch.setattr("apps.payments.services_refund_cases.assess",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db hiccup")))
    event_services.cancel_registration(reg, actor=user, member_cancel=True)
    assert EventRegistration.objects.get(pk=reg.pk).status == "cancelled"
    assert not RefundCase.objects.exists()
    monkeypatch.undo()
    assert rebuild_missed_refund_cases(makerspace_id=space.pk)["opened"] == 1
    assert rebuild_missed_refund_cases(makerspace_id=space.pk)["opened"] == 0  # idempotent
    assert RefundCase.objects.get().payment == payment


def test_paid_booking_cancel_opens_case_in_the_same_transaction():
    space = space_with_currency("hook-booking")
    policy(space, area="bookings", full=24 * 60, partial=0, percent=0, fee="5.00")
    user = member("hook-booking-m", space)
    row, payment = booking(space, user)
    booking_services.cancel_booking(row, actor=user, member_cancel=True)
    case = RefundCase.objects.get(payment=payment)
    assert (case.area, case.reason_code, case.due_amount) == ("bookings", "booking_cancelled", Decimal("25.00"))


def test_booking_cancel_rolls_back_with_its_refund_case(monkeypatch):
    space = space_with_currency("hook-booking-rollback")
    policy(space, area="bookings", full=0, partial=0, percent=0)
    user = member("hook-booking-rb", space)
    row, _ = booking(space, user)
    monkeypatch.setattr("apps.payments.services_refund_cases.record_case",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("audit down")))
    with pytest.raises(RuntimeError):
        booking_services.cancel_booking(row, actor=user, member_cancel=True)
    assert Booking.objects.get(pk=row.pk).status == Booking.Status.CONFIRMED
    assert not RefundCase.objects.exists()


def test_cancel_upgrades_an_open_request_and_a_due_case_is_never_repeated():
    space = space_with_currency("hook-upgrade")
    policy(space, full=0, partial=0, percent=0)
    user = member("hook-upgrade-m", space)
    reg = registration(paid_event(space), user)
    payment = charge(space, user, subject_id=reg.pk)
    asked = request_refund(payment, member=user, reason="Cannot come")
    upgraded = open_due_case(payment, reason_code="registration_cancelled", actor=user)
    assert upgraded.pk == asked.pk and upgraded.kind == "due" and upgraded.due_amount == Decimal("20.00")
    assert upgraded.member_reason == "Cannot come"
    assert open_due_case(payment, reason_code="event_cancelled", actor=None) is None
    assert RefundCase.objects.count() == 1


def test_deposits_and_unsettled_charges_never_open_a_due_case():
    space = space_with_currency("hook-deposit")
    user = member("hook-deposit-m", space)
    held = deposit(space, user)
    pending = charge(space, user, subject_id=registration(paid_event(space), user).pk, status="pending")
    assert open_due_case(held, reason_code="event_cancelled", actor=None) is None
    assert open_due_case(pending, reason_code="event_cancelled", actor=None) is None
    assert not RefundCase.objects.exists()


def test_staff_cancelling_a_members_booking_owes_the_full_amount():
    space = space_with_currency("hook-staff-booking")
    policy(space, area="bookings", full=7 * 24 * 60, partial=24 * 60, percent=50, fee="5.00")
    user, staff = member("hook-staff-booking-m", space), make_member("hook-staff-booking-s", space)
    row, payment = booking(space, user)
    booking_services.cancel_booking(row, actor=staff)
    case = RefundCase.objects.get(payment=payment)
    assert (case.reason_code, case.due_amount) == ("staff_cancelled", Decimal("30.00"))
    assert case.policy_snapshot["rule"] == "staff_cancelled_full"
    own, own_payment = booking(space, member("hook-staff-booking-own", space))
    booking_services.cancel_booking(own, actor=own.member, member_cancel=True)
    own_case = RefundCase.objects.get(payment=own_payment)  # the member's own cancel follows the policy
    assert (own_case.reason_code, own_case.due_amount) == ("booking_cancelled", Decimal("10.00"))


def test_the_sweep_never_looks_before_the_deploy_watermark(monkeypatch):
    from apps.payments import refund_case_sweeper
    space = space_with_currency("hook-watermark")
    policy(space, full=0, partial=0, percent=0)
    user = member("hook-watermark-m", space)
    reg = registration(paid_event(space), user)
    charge(space, user, subject_id=reg.pk)
    monkeypatch.setattr("apps.payments.services_refund_cases.assess",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("hook failed")))
    event_services.cancel_registration(reg, actor=user, member_cancel=True)
    monkeypatch.undo()
    assert refund_case_sweeper.deploy_watermark() is not None  # seeded by the 0023 migration record
    # A cancellation from before the feature was deployed is never back-filled.
    monkeypatch.setattr(refund_case_sweeper, "deploy_watermark", lambda: timezone.now() + timedelta(minutes=1))
    assert rebuild_missed_refund_cases(makerspace_id=space.pk)["opened"] == 0
    monkeypatch.setattr(refund_case_sweeper, "deploy_watermark", lambda: None)
    assert rebuild_missed_refund_cases(makerspace_id=space.pk)["opened"] == 0  # no record: fail closed
    monkeypatch.undo()
    assert rebuild_missed_refund_cases(makerspace_id=space.pk)["opened"] == 1
    assert not RefundCase.objects.exclude(payment__makerspace=space).exists()

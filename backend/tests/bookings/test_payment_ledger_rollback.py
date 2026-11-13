"""Required local debt and booking mutations share the workflow transaction."""

from tests.account_split.sweep_g2_helpers import ledger_booking as build_ledger_booking

from unittest.mock import Mock

import pytest
from django.db import IntegrityError

from apps.bookings import service_payments, services_bookings
from apps.bookings.models import BookableSpace, Booking
from apps.bookings.services_recurrence import create_recurring_bookings
from apps.payments.models import Payment
from tests.bookings.payment_ledger_helpers import (
    create_booking, fail_ledger, ledger_state,
)

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("workflow", ["instant", "approval", "recurring"])
@pytest.mark.parametrize("failure", ["lookup", "write", "audit"])
def test_required_creation_failure_rolls_back_entire_workflow(
    ledger_booking, monkeypatch, django_capture_on_commit_callbacks, workflow, failure,
):
    makerspace, space, member, manager = ledger_booking
    if workflow == "approval":
        space.approval_mode = BookableSpace.ApprovalMode.APPROVE
        space.save(update_fields=["approval_mode"])
        booking = create_booking(space, member)
    before = ledger_state()
    fail_ledger(monkeypatch, failure)

    with django_capture_on_commit_callbacks() as callbacks:
        with pytest.raises(RuntimeError, match="required ledger"):
            if workflow == "instant":
                create_booking(space, member)
            elif workflow == "approval":
                services_bookings.approve_booking(booking, actor=manager)
            else:
                from datetime import timedelta
                from django.utils import timezone

                start = timezone.now() + timedelta(days=1)
                create_recurring_bookings(
                    space, actor=manager, member=member, count=2,
                    starts_at=start, ends_at=start + timedelta(hours=1),
                )

    assert ledger_state() == before
    assert callbacks == []
    assert makerspace.enabled_modules == ["bookings"]


def test_later_recurring_debt_failure_rolls_back_earlier_occurrence(
    ledger_booking, monkeypatch, django_capture_on_commit_callbacks,
):
    from datetime import timedelta
    from django.utils import timezone

    _, space, member, manager = ledger_booking
    before = ledger_state()
    original = service_payments.create_payment
    calls = []

    def create(**kwargs):
        payment = original(**kwargs)
        calls.append(payment.pk)
        if len(calls) == 2:
            raise RuntimeError("second debt failed")
        return payment

    monkeypatch.setattr(service_payments, "create_payment", create)
    start = timezone.now() + timedelta(days=1)
    with django_capture_on_commit_callbacks() as callbacks:
        with pytest.raises(RuntimeError, match="second debt failed"):
            create_recurring_bookings(
                space, actor=manager, member=member, count=2,
                starts_at=start, ends_at=start + timedelta(hours=1),
            )
    assert len(calls) == 2
    assert ledger_state() == before
    assert callbacks == []


@pytest.mark.parametrize("member_cancel", [False, True])
@pytest.mark.parametrize("failure", ["lookup", "write", "audit"])
def test_required_cancellation_failure_restores_booking_charge_and_calendar(
    ledger_booking, monkeypatch, django_capture_on_commit_callbacks, member_cancel, failure,
):
    _, space, member, manager = ledger_booking
    booking = create_booking(space, member)
    before = ledger_state()
    fail_ledger(monkeypatch, failure)

    with django_capture_on_commit_callbacks() as callbacks:
        with pytest.raises(RuntimeError, match="required ledger"):
            services_bookings.cancel_booking(
                booking, actor=member if member_cancel else manager,
                member_cancel=member_cancel,
            )

    assert ledger_state() == before
    assert callbacks == []


def test_unrelated_integrity_error_cannot_confirm_without_debt(
    ledger_booking, monkeypatch, django_capture_on_commit_callbacks,
):
    _, space, member, _ = ledger_booking
    before = ledger_state()
    monkeypatch.setattr(
        service_payments, "create_payment", Mock(side_effect=IntegrityError("insert failed")),
    )
    with django_capture_on_commit_callbacks() as callbacks:
        with pytest.raises(Payment.DoesNotExist):
            create_booking(space, member)
    assert ledger_state() == before
    assert callbacks == []


@pytest.mark.parametrize("unique_conflict", [False, True])
def test_confirmation_subject_is_idempotent_including_unique_conflict_recovery(
    ledger_booking, monkeypatch, unique_conflict,
):
    from django.db.models.query import QuerySet

    _, space, member, manager = ledger_booking
    booking = create_booking(space, member)
    payment = Payment.objects.get(subject_id=booking.pk)
    before = ledger_state()
    if unique_conflict:
        original = QuerySet.first

        def first(queryset):
            # Simulate a stale initial read followed by a competing subject insert.
            return None if queryset.model is Payment else original(queryset)

        monkeypatch.setattr(QuerySet, "first", first)
        monkeypatch.setattr(
            service_payments, "create_payment",
            Mock(side_effect=IntegrityError("payment_one_per_subject")),
        )
    for _ in range(2):
        assert service_payments.create_for_confirmed_booking(booking, manager).pk == payment.pk
    assert ledger_state() == before
    assert payment.provider == Payment.Provider.UNCLAIMED
    assert payment.status == Payment.Status.PENDING


@pytest.mark.parametrize("reason", ["zero_price", "tracking_off", "no_member"])
def test_nonchargeable_confirmation_does_not_touch_ledger(
    ledger_booking, monkeypatch, reason,
):
    makerspace, space, member, _ = ledger_booking
    if reason == "zero_price":
        space.payment_amount = 0
        space.save(update_fields=["payment_amount"])
    elif reason == "tracking_off":
        makerspace.enabled_features = []
        makerspace.save(update_fields=["enabled_features"])
    lookup = Mock(side_effect=AssertionError("no required debt"))
    monkeypatch.setattr(service_payments, "_get_or_create", lookup)
    if reason == "no_member":
        from datetime import timedelta
        from django.utils import timezone

        start = timezone.now() + timedelta(days=1)
        booking = services_bookings.create_booking(
            space, starts_at=start, ends_at=start + timedelta(hours=1),
            name="Legacy contact", email="legacy@example.com", phone="+919999999999",
        )
    else:
        booking = create_booking(space, member)
    assert booking.status == Booking.Status.CONFIRMED
    assert not Payment.objects.filter(subject_id=booking.pk).exists()
    lookup.assert_not_called()


@pytest.fixture
def ledger_booking():
    return build_ledger_booking()

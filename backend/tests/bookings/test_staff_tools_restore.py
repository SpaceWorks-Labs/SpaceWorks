"""Exact, five-minute undo is a fresh admission and never reopens money."""

from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from rest_framework.exceptions import ValidationError

from apps.audit.models import AuditLog
from apps.bookings import services
from apps.bookings.exceptions import BookingConflict, BookingInvalidTransition
from apps.bookings.models import Booking
from apps.makerspaces.models import MakerspaceMembership, MakerspaceWaiver
from apps.operations.cancellation_restore import RestoreRefused
from apps.payments.availability import charge_tracking_enabled
from apps.payments.models import Payment
from apps.payments.reconciliation import mark_offline, waive
from apps.payments.services import create_payment
from apps.payments.services_webhooks import apply_webhook_event
from apps.payments.services_refunds_offline import record_offline_refund
from apps.presence.guard import MemberPresenceRequired, WaiverAcceptanceRequired
from tests.bookings.test_staff_tools_helpers import NOW, reserve, snapshot, world
from tests.bookings.staff_grant_helpers import service_manager
from tests.return_helpers import settlement_details

pytestmark = pytest.mark.django_db


def refuse(w, reason):
    before = snapshot(w)
    with pytest.raises(RestoreRefused) as failure:
        services.restore_booking(w.row, actor=w.grantee)
    assert str(failure.value.detail["code"]) == reason
    assert snapshot(w) == before


@pytest.mark.parametrize("status", ["pending", "confirmed"])
def test_real_cancel_then_restore_preserves_identity_and_exact_state(monkeypatch, status):
    w = world(monkeypatch, status=status)
    original = snapshot(w)[0]
    w.row = services.cancel_booking(w.row, actor=w.grantee)
    assert w.row.status_before_cancel == status and w.row.cancelled_at == NOW
    cancelled_sequence = w.row.calendar_sequence
    restored = services.restore_booking(w.row, actor=w.grantee)
    assert (restored.pk, restored.public_token, restored.created_at, restored.starts_at, restored.ends_at) == (
        original["id"], original["public_token"], original["created_at"], original["starts_at"], original["ends_at"],
    )
    assert restored.status == status and restored.cancelled_at is None and restored.status_before_cancel == ""
    assert restored.calendar_sequence == cancelled_sequence + 1
    assert AuditLog.objects.get(action="booking.restored").actor == w.grantee
    assert not Payment.objects.filter(makerspace=w.tenant).exists()


@pytest.mark.parametrize("seconds,allowed", [(0, True), (299.999, True), (300, False), (301, False), (-1, False)])
def test_five_minute_window_uses_strict_server_clock_boundary(monkeypatch, seconds, allowed):
    w = world(monkeypatch)
    w.row = services.cancel_booking(w.row, actor=w.actor)
    monkeypatch.setattr("django.utils.timezone.now", lambda: NOW + timedelta(seconds=seconds))
    if allowed:
        assert services.restore_booking(w.row, actor=w.grantee).status == "confirmed"
    else:
        refuse(w, "window_expired")


@pytest.mark.parametrize("provenance", ["null_date", "blank_prior", "terminal_prior"])
def test_legacy_or_ineligible_provenance_is_never_guessed(monkeypatch, provenance):
    w = world(monkeypatch)
    w.row = services.cancel_booking(w.row, actor=w.actor)
    values = {"cancelled_at": None} if provenance == "null_date" else {
        "status_before_cancel": "completed" if provenance == "terminal_prior" else "",
    }
    Booking.objects.filter(pk=w.row.pk).update(**values)
    refuse(w, "missing_provenance")


def test_live_row_and_double_undo_refuse_without_extra_calendar_revision(monkeypatch):
    w = world(monkeypatch)
    refuse(w, "not_cancelled")
    w.row = services.cancel_booking(w.row, actor=w.actor)
    services.restore_booking(w.row, actor=w.actor)
    refuse(w, "not_cancelled")


@pytest.mark.parametrize("state", list(Payment.Status.values))
def test_every_historical_ledger_status_blocks_restore(monkeypatch, state):
    if state == "paid_online":
        # Provider configuration is an external boundary. Keep real charge insertion,
        # verified-event settlement, receipt creation and cancellation transactions.
        source = SimpleNamespace(vendor="stripe", provider="raw", connected_account_id=None, application_fee_bps=0)
        monkeypatch.setattr("apps.payments.services.resolve_payment_source", lambda tenant: source)
    w = world(monkeypatch, charged=True)
    payment = Payment.objects.get(makerspace=w.tenant, subject_type="booking", subject_id=w.row.pk)
    # Drive actual debt creation first. Provider/reconciliation terminal states remain
    # valid history even when the resource's current price is subsequently zero.
    if state == "paid_offline":
        payment = mark_offline(payment, w.actor, settlement=settlement_details())
    elif state == "waived":
        payment = waive(payment, w.actor)
    elif state == "paid_online":
        payment.stripe_payment_intent_id = "pi_restore_history"
        payment.save(update_fields=["stripe_payment_intent_id"])
        payment = apply_webhook_event(w.tenant, {"id": "evt_restore_history", "type": "payment_intent.succeeded",
                                               "data": {"object": {"id": "pi_restore_history"}}})
        assert payment.status == "paid_online"
    w.row = services.cancel_booking(w.row, actor=w.actor)
    if state == "pending":
        # A pending debt may be raised later through the core ledger service against
        # a legacy cancellation; use a separate subject so no terminal row is mutated.
        free = world_for_pending_history(w)
        w.row = free
        payment = create_payment(makerspace=w.tenant, subject_type="booking", subject_id=free.pk,
                                 member=w.member, amount=Decimal("1.00"), currency="usd", created_by=w.actor)
    w.resource.payment_amount = 0
    w.resource.save(update_fields=["payment_amount"])
    refuse(w, "historical_charge")
    payment.refresh_from_db()
    assert payment.status == ("canceled" if state == "canceled" else state)


def world_for_pending_history(w):
    w.resource.payment_amount = 0
    w.resource.save(update_fields=["payment_amount"])
    return services.cancel_booking(reserve(w), actor=w.actor)


def test_fully_refunded_history_still_refuses_without_reopening_original_debt(monkeypatch):
    w = world(monkeypatch, charged=True)
    payment = Payment.objects.get(makerspace=w.tenant, subject_type="booking", subject_id=w.row.pk)
    payment = mark_offline(payment, w.actor, settlement=settlement_details())
    refund = record_offline_refund(payment, amount=str(payment.amount), reason="Returned payment", actor=service_manager(),
                                  receipt={"method": "cash", "reference": "refund-1", "refunded_at": NOW})
    assert refund.status == "succeeded" and refund.amount == payment.amount
    w.row = services.cancel_booking(w.row, actor=w.actor)
    refuse(w, "historical_charge")
    payment.refresh_from_db()
    assert payment.status == "paid_offline"


def test_current_new_price_cannot_create_a_charge_during_undo(monkeypatch):
    w = world(monkeypatch)
    w.row = services.cancel_booking(w.row, actor=w.actor)
    w.resource.payment_amount = 25
    w.resource.save(update_fields=["payment_amount"])
    refuse(w, "charge_required")
    assert not Payment.objects.filter(makerspace=w.tenant).exists()


@pytest.mark.parametrize("priced_at_creation", [True, False])
def test_priced_pending_restore_needs_no_charge(monkeypatch, priced_at_creation):
    w = world(monkeypatch, status="pending", charged=priced_at_creation)
    assert charge_tracking_enabled(w.tenant, "bookings")
    assert w.row.status == "pending"
    assert not Payment.objects.filter(makerspace=w.tenant).exists()
    original = snapshot(w)[0]
    w.row = services.cancel_booking(w.row, actor=w.grantee)
    if not priced_at_creation:
        w.resource.payment_amount = 12
        w.resource.save(update_fields=["payment_amount"])
    cancelled_sequence = w.row.calendar_sequence
    restored = services.restore_booking(w.row, actor=w.grantee)
    assert restored.status == "pending"
    assert (restored.pk, restored.public_token, restored.created_at) == (
        original["id"], original["public_token"], original["created_at"],
    )
    assert restored.cancelled_at is None and restored.status_before_cancel == ""
    assert restored.calendar_sequence == cancelled_sequence + 1
    assert AuditLog.objects.get(action="booking.restored").actor == w.grantee
    assert not Payment.objects.filter(makerspace=w.tenant).exists()


def test_priced_pending_restore_still_refuses_historical_charge(monkeypatch):
    w = world(monkeypatch, status="pending", charged=True)
    payment = create_payment(makerspace=w.tenant, subject_type="booking", subject_id=w.row.pk,
                             member=w.member, amount=Decimal("12.00"), currency="usd", created_by=w.actor)
    w.row = services.cancel_booking(w.row, actor=w.grantee)
    payment.refresh_from_db()
    assert payment.status == "canceled"
    refuse(w, "historical_charge")


@pytest.mark.parametrize("status", ["pending", "confirmed"])
def test_policy_change_cannot_upgrade_or_downgrade_cancelled_state(monkeypatch, status):
    w = world(monkeypatch, status=status)
    w.row = services.cancel_booking(w.row, actor=w.actor)
    w.resource.approval_mode = "instant" if status == "pending" else "approve"
    w.resource.save(update_fields=["approval_mode"])
    refuse(w, "admission_changed")


def test_confirmed_restore_rechecks_conflict_but_pending_restore_has_no_occupancy(monkeypatch):
    w = world(monkeypatch)
    w.row = services.cancel_booking(w.row, actor=w.actor)
    reserve(w, starts_at=w.row.starts_at)
    before = snapshot(w)
    with pytest.raises(BookingConflict):
        services.restore_booking(w.row, actor=w.actor)
    assert snapshot(w) == before
    w.resource.approval_mode = "approve"
    w.resource.save(update_fields=["approval_mode"])
    pending = reserve(w, starts_at=w.row.starts_at)
    pending = services.cancel_booking(pending, actor=w.actor)
    assert services.restore_booking(pending, actor=w.grantee).status == "pending"


@pytest.mark.parametrize("gate", ["resource", "owner", "membership", "waiver", "duration", "lead", "horizon", "closed", "dump_stub"])
def test_restore_repeats_current_admission_and_rolls_back_on_refusal(monkeypatch, gate):
    w = world(monkeypatch)
    w.row = services.cancel_booking(w.row, actor=w.actor)
    if gate == "owner":
        w.member.is_active = False
        w.member.save(update_fields=["is_active"])
    elif gate == "dump_stub":
        type(w.member).objects.filter(pk=w.member.pk).update(is_tenant_dump_stub=True)
    elif gate == "membership":
        MakerspaceMembership.objects.filter(makerspace=w.tenant, user=w.member).update(status="revoked")
    elif gate == "waiver":
        MakerspaceWaiver.objects.create(makerspace=w.tenant, body="New waiver", version="v3", is_active=True)
    elif gate == "closed":
        w.tenant.opening_hours = {"weekly": {}, "exceptions": {w.row.starts_at.date().isoformat(): []}}
        w.tenant.save(update_fields=["opening_hours"])
    else:
        field, value = {"resource": ("is_active", False), "duration": ("min_booking_duration_minutes", 120),
                        "lead": ("booking_lead_time_minutes", 10000), "horizon": ("max_booking_advance_days", 1)}[gate]
        setattr(w.resource, field, value)
        w.resource.save(update_fields=[field])
    before = snapshot(w)
    with pytest.raises((BookingInvalidTransition, ValidationError, MemberPresenceRequired, WaiverAcceptanceRequired)):
        services.restore_booking(w.row, actor=w.grantee)
    assert snapshot(w) == before


def test_required_cancel_ledger_failure_rolls_back_new_provenance_and_callbacks(monkeypatch, django_capture_on_commit_callbacks):
    w = world(monkeypatch, charged=True)
    before = snapshot(w)
    def fail(*args, **kwargs):
        raise RuntimeError("required cancel failed")
    monkeypatch.setattr("apps.bookings.service_payments.cancel_or_hold", fail)
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        with pytest.raises(RuntimeError, match="required cancel failed"):
            services.cancel_booking(w.row, actor=w.actor)
    assert snapshot(w) == before and callbacks == []

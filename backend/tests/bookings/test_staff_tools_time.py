"""Staff moves preserve lifecycle/money and repeat current admission under locks."""

from datetime import datetime, timedelta, timezone as dt_timezone

import pytest
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.bookings import services
from apps.bookings.exceptions import BookingConflict, BookingInvalidTransition
from apps.bookings.models import Booking
from apps.makerspaces.models import MakerspaceMembership
from apps.makerspaces.waiver_services import publish_waiver
from apps.operations.reports_bookings import build_booking_utilization
from apps.payments.models import Payment
from apps.presence.guard import MemberPresenceRequired, WaiverAcceptanceRequired
from tests.bookings.test_staff_tools_helpers import NOW, reserve, snapshot, world
from tests.machines.certification_helpers import _certification, _machine_type

pytestmark = pytest.mark.django_db


def move(w, *, start=None, duration=60, actor=None):
    start = start or NOW + timedelta(days=3)
    return services.edit_booking_time(w.row, actor=actor or w.grantee,
                                      starts_at=start, ends_at=start + timedelta(minutes=duration))


@pytest.mark.parametrize("status", ["pending", "confirmed"])
def test_pending_confirmed_move_keeps_identity_status_and_flat_charge(monkeypatch, status):
    w = world(monkeypatch, status=status, charged=True)
    before, payments, audits = snapshot(w)
    if status == "confirmed":
        assert len(payments) == 1 and payments[0]["status"] == "pending"
    moved = move(w)
    after, current_payments, current_audits = snapshot(w)
    assert (moved.pk, moved.public_token, moved.member_id, moved.space_id, moved.status, moved.created_at) == (
        w.row.pk, w.row.public_token, w.member.pk, w.resource.pk, status, w.row.created_at,
    )
    assert moved.calendar_sequence == before["calendar_sequence"] + 1
    assert moved.calendar_updated_at == NOW and moved.starts_at == NOW + timedelta(days=3)
    assert current_payments == payments
    assert len(current_audits) == len(audits) + 1 and current_audits[-1]["action"] == "booking.rescheduled"


@pytest.mark.parametrize("boundary", ["old_equal", "new_equal", "old_started", "old_ended", "new_started", "negative_duration"])
def test_old_and_new_cutoff_equalities_and_started_windows_refuse_without_history_changes(monkeypatch, boundary):
    w = world(monkeypatch, charged=True)
    w.resource.cancellation_cutoff_hours = 2
    w.resource.booking_lead_time_minutes = 0
    w.resource.save(update_fields=["cancellation_cutoff_hours", "booking_lead_time_minutes"])
    if boundary.startswith("old"):
        start = NOW + timedelta(hours=2) if boundary == "old_equal" else NOW - timedelta(hours=1)
        end = NOW + timedelta(hours=1) if boundary == "old_started" else start + timedelta(minutes=30)
        Booking.objects.filter(pk=w.row.pk).update(starts_at=start, ends_at=end)
    before = snapshot(w)
    reports = build_booking_utilization(w.tenant.pk)
    proposed = NOW + timedelta(hours=2) if boundary == "new_equal" else NOW if boundary == "new_started" else NOW + timedelta(days=3)
    with pytest.raises((BookingInvalidTransition, ValidationError)):
        move(w, start=proposed, duration=-1 if boundary == "negative_duration" else 60)
    assert snapshot(w) == before
    assert build_booking_utilization(w.tenant.pk) == reports


@pytest.mark.parametrize("status", ["rejected", "cancelled", "completed", "no_show"])
def test_terminal_reservation_cannot_be_moved_into_future(monkeypatch, status):
    w = world(monkeypatch, charged=True)
    Booking.objects.filter(pk=w.row.pk).update(status=status)
    before = snapshot(w)
    report = build_booking_utilization(w.tenant.pk)
    with pytest.raises(BookingInvalidTransition):
        move(w)
    assert snapshot(w) == before and build_booking_utilization(w.tenant.pk) == report


@pytest.mark.parametrize("field,value", [
    ("min_booking_duration_minutes", 90), ("max_booking_duration_minutes", 30),
    ("booking_lead_time_minutes", 60 * 24 * 4), ("max_booking_advance_days", 1), ("is_active", False),
])
def test_staff_move_rechecks_changed_current_rules(monkeypatch, field, value):
    w = world(monkeypatch)
    setattr(w.resource, field, value)
    w.resource.save(update_fields=[field])
    before = snapshot(w)
    with pytest.raises((BookingInvalidTransition, ValidationError)):
        move(w)
    assert snapshot(w) == before


@pytest.mark.parametrize("status", ["pending", "confirmed"])
def test_moves_check_other_confirmations_and_combined_buffer_boundaries(monkeypatch, status):
    w = world(monkeypatch, status=status)
    w.resource.approval_mode = "instant"
    w.resource.buffer_before_minutes = 10
    w.resource.buffer_after_minutes = 20
    w.resource.save(update_fields=["approval_mode", "buffer_before_minutes", "buffer_after_minutes"])
    incumbent = reserve(w)
    before = snapshot(w)
    with pytest.raises(BookingConflict):
        move(w, start=incumbent.ends_at + timedelta(minutes=29))
    assert snapshot(w) == before
    moved = move(w, start=incumbent.ends_at + timedelta(minutes=30))
    assert moved.status == status
    # A no-op move must exclude this booking from conflict detection.
    assert move(w, start=moved.starts_at).pk == moved.pk


def test_time_edit_respects_entire_open_window_including_cleanup(monkeypatch):
    w = world(monkeypatch)
    w.resource.buffer_before_minutes = 15
    w.resource.buffer_after_minutes = 15
    w.resource.save(update_fields=["buffer_before_minutes", "buffer_after_minutes"])
    day = (NOW + timedelta(days=3)).date().isoformat()
    w.tenant.opening_hours = {"weekly": {}, "exceptions": {day: [{"start": "10:00", "end": "12:00"}]}}
    w.tenant.save(update_fields=["opening_hours"])
    before = snapshot(w)
    with pytest.raises(ValidationError):
        move(w)
    assert snapshot(w) == before
    assert move(w, start=NOW + timedelta(days=3, minutes=15), duration=90).ends_at == NOW + timedelta(days=3, hours=1, minutes=45)


def test_staff_move_uses_actual_elapsed_dst_time_in_tenant_open_hours(monkeypatch):
    w = world(monkeypatch)
    begins = datetime(2030, 3, 10, 6, tzinfo=dt_timezone.utc)
    monkeypatch.setattr("django.utils.timezone.now", lambda: begins - timedelta(days=1))
    Booking.objects.filter(pk=w.row.pk).update(starts_at=begins + timedelta(days=1), ends_at=begins + timedelta(days=1, hours=1))
    w.tenant.timezone = "America/New_York"
    w.tenant.opening_hours = {"weekly": {}, "exceptions": {"2030-03-10": [{"start": "01:00", "end": "04:00"}]}}
    w.tenant.save(update_fields=["timezone", "opening_hours"])
    before = snapshot(w)
    with pytest.raises(ValidationError):
        move(w, start=begins, duration=121)
    assert snapshot(w) == before
    assert move(w, start=begins, duration=120).ends_at == begins + timedelta(hours=2)


@pytest.mark.parametrize("gate", ["account", "membership", "waiver", "certification", "missing_owner", "dump_stub"])
def test_staff_grant_cannot_override_owner_eligibility_waiver_or_training(monkeypatch, gate):
    w = world(monkeypatch)
    if gate == "account":
        w.member.access_status = "suspended"
        w.member.save(update_fields=["access_status"])
    elif gate == "dump_stub":
        type(w.member).objects.filter(pk=w.member.pk).update(is_tenant_dump_stub=True)
    elif gate == "membership":
        MakerspaceMembership.objects.filter(makerspace=w.tenant, user=w.member).update(status="revoked")
    elif gate == "waiver":
        publish_waiver(w.actor, w.tenant, "New terms", "v2")
    elif gate == "certification":
        w.tenant.enabled_features.append("machines.certifications")
        w.tenant.save(update_fields=["enabled_features"])
        machine_type = _machine_type(w.tenant)
        _certification(w.tenant, machine_type)
        w.resource.machine_type = machine_type
        w.resource.save(update_fields=["machine_type"])
    else:
        Booking.objects.filter(pk=w.row.pk).update(member=None)
    before = snapshot(w)
    with pytest.raises((PermissionDenied, BookingInvalidTransition, MemberPresenceRequired, WaiverAcceptanceRequired)):
        move(w)
    assert snapshot(w) == before
    assert not Payment.objects.filter(makerspace=w.tenant).exists()

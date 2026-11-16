"""Open items A24 (EB12/BK3 today counters) and A31 (U13 per-area failures)."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.bookings.models import BookableSpace, Booking
from apps.events.models import Event
from apps.inventory.models import InventoryProduct
from apps.operations.views_dashboard_counts import build_dashboard
from tests.account_split.p1_helpers import staff
from tests.fixed_roles.helpers import assign_builtin_roles
from tests.modules.family_helpers import account, client, family_space

pytestmark = pytest.mark.django_db


def _event(space, starts_at, hours=1):
    return Event.objects.create(makerspace=space, title="Workshop", starts_at=starts_at,
                                ends_at=starts_at + timedelta(hours=hours), status="published")


def test_today_events_and_bookings_count_only_the_local_day_and_own_space():
    space = family_space("dash-today", "events", "bookings")
    other = family_space("dash-today-foreign", "events", "bookings")
    now = timezone.now()
    for tenant in (space, other):
        _event(tenant, now - timedelta(minutes=30))
        room = BookableSpace.objects.create(makerspace=tenant, name="Room")
        Booking.objects.create(space=room, name="Visitor", email="v@example.test", phone="1",
                               starts_at=now - timedelta(minutes=10), ends_at=now + timedelta(minutes=50),
                               status="confirmed")
    _event(space, now + timedelta(days=3))
    counts = build_dashboard(space)
    assert counts["today_events"] == 1
    assert counts["today_check_ins"] == 0
    assert counts["today_bookings"] == 1
    assert counts["upcoming_events"] == 2
    assert counts["failed_areas"] == []


def test_event_manager_gets_today_counts_and_booking_tiles_stay_hidden():
    space = family_space("dash-today-role", "events", "bookings")
    actor, _ = staff(space, "dash-today-staff", access_status="active")
    assign_builtin_roles(actor, space, "event_manager")
    _event(space, timezone.now() - timedelta(minutes=5))
    result = client(actor).get(f"/api/v1/admin/makerspace/{space.pk}/dashboard")
    assert result.status_code == 200, result.data
    assert result.data["today_events"] == 1
    assert result.data["today_bookings"] == 0
    assert result.data["room_outages_week"] == 0


def test_failing_area_is_named_and_others_still_count(monkeypatch, caplog):
    space = family_space("dash-failed-area", "events", "bookings", loans=True)
    room = BookableSpace.objects.create(makerspace=space, name="Room")
    start = timezone.now() + timedelta(days=1)
    Booking.objects.create(space=room, starts_at=start, ends_at=start + timedelta(hours=1),
                           name="Visitor", email="visitor@example.test", phone="1", status="pending")

    def unavailable(*args, **kwargs):
        raise RuntimeError("private-contact@example.test")

    monkeypatch.setattr(Event.objects, "filter", unavailable)
    monkeypatch.setattr(InventoryProduct.objects, "filter", unavailable)
    counts = build_dashboard(space)
    assert "events" in counts["failed_areas"] and "inventory" in counts["failed_areas"]
    assert "bookings" not in counts["failed_areas"]
    assert counts["pending_bookings"] == 1
    assert "private-contact" not in caplog.text


def test_failed_areas_is_in_the_api_payload():
    space = family_space("dash-failed-payload", loans=True)
    actor = account("dash-failed-payload-owner")
    assign_builtin_roles(actor, space, "space_manager")
    result = client(actor).get(f"/api/v1/admin/makerspace/{space.pk}/dashboard")
    assert result.status_code == 200, result.data
    assert result.data["failed_areas"] == []

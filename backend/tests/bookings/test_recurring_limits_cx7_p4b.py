"""Monthly batch refusal is atomic; the established live-cap result is per occurrence."""
from datetime import timedelta

import pytest
from django.db import connection
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.bookings.models import Booking
from apps.payments.models import Payment
from tests.bookings.test_booking_limits_cx7_p4b import setup, snapshot
from tests.inventory.test_creator_limit_concurrency_cx7 import callers
from tests.limits_0120.concurrency_helpers_cx7 import race_posts

pytestmark = [pytest.mark.django_db, pytest.mark.area_bookings]


def scenario(key, surface, settings, monkeypatch):
    w = setup("staff", key)
    space, _, room, member, _, _ = w
    space.enabled_features = sorted(set(space.enabled_features) | {"bookings.recurring"})
    space.resource_limit_overrides = {key: 2}
    space.save(update_fields=["enabled_features", "resource_limit_overrides"])
    pair = callers(space, surface, settings, monkeypatch)
    start = timezone.now() + timedelta(days=2)
    bodies = [{"member_id": member.pk, "count": 2, "starts_at": (start + timedelta(days=index)).isoformat(),
               "ends_at": (start + timedelta(days=index, hours=1)).isoformat()} for index in range(2)]
    return space, room, pair, bodies


@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_recurring_monthly_max_next_exact_refusal_rolls_back_whole_batch(surface, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    space, room, pair, bodies = scenario("bookings_monthly", surface, settings, monkeypatch)
    url = reverse("admin-recurring-bookings", kwargs={"pk": room.pk})
    maximum = pair[0].post(url, bodies[0], format="json")
    assert maximum.status_code == 200
    assert [row["status"] for row in maximum.json()["occurrences"]] == ["confirmed", "confirmed"]
    before = snapshot()
    refused = pair[1].post(url, bodies[1], format="json")
    assert (refused.status_code, refused.json()["code"]) == (409, "booking_quota_reached")
    assert snapshot() == before
    assert Booking.objects.filter(space__makerspace=space).count() == 2
    assert Payment.objects.filter(makerspace=space).count() == 0


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_two_recurring_batches_compete_for_one_remaining_monthly_batch(surface, settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    space, room, pair, bodies = scenario("bookings_monthly", surface, settings, monkeypatch)
    results = race_posts(pair, reverse("admin-recurring-bookings", kwargs={"pk": room.pk}), bodies)
    assert sorted(status for status, _ in results) == [200, 409]
    assert [body["code"] for status, body in results if status == 409] == ["booking_quota_reached"]
    assert Booking.objects.filter(space__makerspace=space).count() == 2
    assert AuditLog.objects.filter(makerspace=space, action="booking.recurrence_created").count() == 1


def test_recurring_active_cap_returns_two_explicit_conflicts_without_new_bookings(settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    space, room, pair, bodies = scenario("bookings", "browser", settings, monkeypatch)
    url = reverse("admin-recurring-bookings", kwargs={"pk": room.pk})
    assert pair[0].post(url, bodies[0], format="json").status_code == 200
    rows = list(Booking.objects.order_by("pk").values())
    result = pair[1].post(url, bodies[1], format="json")
    assert result.status_code == 200  # established partial-batch contract, not a typed HTTP refusal
    occurrences = result.json()["occurrences"]
    assert [row["status"] for row in occurrences] == ["conflict", "conflict"]
    assert [row["booking_id"] for row in occurrences] == [None, None]
    assert all("code='limit_reached'" in row["detail"] for row in occurrences)
    assert list(Booking.objects.order_by("pk").values()) == rows
    assert AuditLog.objects.filter(makerspace=space, action="booking.recurrence_created").count() == 2


@pytest.mark.parametrize("switch", ["bookings", "bookings.recurring"])
def test_recurring_switch_off_keeps_rows_and_on_restores_full_batch(switch, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    space, room, pair, bodies = scenario("bookings_monthly", "browser", settings, monkeypatch)
    field = "enabled_features" if "." in switch else "enabled_modules"
    saved = getattr(space, field)
    setattr(space, field, [value for value in saved if value != switch])
    space.save(update_fields=[field])
    before = snapshot()
    url = reverse("admin-recurring-bookings", kwargs={"pk": room.pk})
    refused = pair[0].post(url, bodies[0], format="json")
    assert (refused.status_code, refused.json()["code"]) == (404, "feature_disabled" if "." in switch else "module_disabled")
    assert snapshot() == before
    setattr(space, field, saved)
    space.save(update_fields=[field])
    assert pair[0].post(url, bodies[0], format="json").status_code == 200

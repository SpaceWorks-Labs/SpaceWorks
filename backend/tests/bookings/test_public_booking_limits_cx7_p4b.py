"""Public booking on browser and attested native clients shares the creator quotas."""
from datetime import timedelta

import pytest
from django.db import connection
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.bookings.models import Booking
from tests.bookings.test_booking_limits_cx7_p4b import setup, snapshot
from tests.limits_0120.concurrency_helpers_cx7 import race_posts
from tests.machines.test_intake_limits_cx7_p4b import member_client
from tests.return_helpers import authenticated_client

pytestmark = [pytest.mark.django_db, pytest.mark.area_bookings]


def scenario(key, surface, settings, monkeypatch):
    w = setup("member", key)
    space, _, room, person, _, _ = w
    room.is_public = True
    room.save(update_fields=["is_public"])
    first = member_client(person, surface, settings, monkeypatch, space.pk)
    second = authenticated_client(person) if surface == "browser" else APIClient()
    if surface != "browser":
        second.credentials(**first._credentials)
    url = reverse("public-booking-submit", kwargs={"makerspace_slug": space.slug, "public_token": room.public_token})
    start = timezone.now() + timedelta(days=3)
    bodies = [{"starts_at": (start + timedelta(days=index)).isoformat(),
               "ends_at": (start + timedelta(days=index, hours=1)).isoformat()} for index in range(2)]
    return space, [first, second], url, bodies


@pytest.mark.parametrize("key", ["bookings", "bookings_monthly"])
@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_public_booking_max_next_exact_refusal_has_no_writes(key, surface, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    space, pair, url, bodies = scenario(key, surface, settings, monkeypatch)
    assert pair[0].post(url, bodies[0], format="json").status_code == 201
    before = snapshot()
    refused = pair[1].post(url, bodies[1], format="json")
    assert (refused.status_code, refused.json()["code"]) == ((400, "limit_reached") if key == "bookings"
                                                          else (409, "booking_quota_reached"))
    assert snapshot() == before
    assert Booking.objects.filter(space__makerspace=space).count() == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("key", ["bookings", "bookings_monthly"])
@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_public_bookers_racing_at_last_slot_have_one_winner(key, surface, settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    settings.MANAGED_PLANS_ENABLED = False
    space, pair, url, bodies = scenario(key, surface, settings, monkeypatch)
    results = race_posts(pair, url, bodies)
    refused = 400 if key == "bookings" else 409
    assert sorted(status for status, _ in results) == [201, refused]
    assert [body["code"] for status, body in results if status == refused] == [
        "limit_reached" if key == "bookings" else "booking_quota_reached"]
    assert Booking.objects.filter(space__makerspace=space).count() == 1
    assert AuditLog.objects.filter(makerspace=space, action="booking.created").count() == 1

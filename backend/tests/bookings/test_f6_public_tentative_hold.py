"""Final audit 0.12.0 (m22): a PENDING event hold shows on public availability as a neutral tentative
block and never names its booker, even where the room publishes booker names."""
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.bookings.models import Booking
from tests.bookings.admin_api_helpers import booking, space, tenant

pytestmark = pytest.mark.django_db


def test_pending_hold_is_tentative_and_unnamed(monkeypatch):
    makerspace = tenant("f6-hold")
    room = space(makerspace, show_public_availability=True, show_public_booker_names=True)
    start = timezone.now() + timedelta(days=2)
    confirmed = booking(room, starts_at=start, name="Confirmed Carl")
    hold = booking(room, starts_at=start + timedelta(hours=3), name="Pending Pat", status=Booking.Status.PENDING)
    monkeypatch.setattr("apps.bookings.event_holds.tentative_booking_ids", lambda *a, **k: [hold.pk])
    url = reverse("public-space-availability",
                  kwargs={"makerspace_slug": makerspace.slug, "public_token": room.public_token})
    response = APIClient().get(url, {"starts_at": start - timedelta(hours=1), "ends_at": start + timedelta(days=1)})
    assert response.status_code == 200
    rows = {row["tentative"]: row for row in response.data["availability"]}
    assert rows[False]["booker_name"] == confirmed.name
    assert rows[True]["booker_name"] is None
    assert "Pending Pat" not in str(response.data)

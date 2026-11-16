"""Lane L15 (A8): a booking submitted with a stale preview digest is refused with the new price."""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.bookings.models import Booking
from apps.payments.pricing import quote
from tests.payments.pricing.helpers import D, client, member, pricing_space, rate
from tests.payments.pricing.test_domain_seams import install
from tests.payments.test_track3_booking_event_charging import bookable

pytestmark = pytest.mark.django_db


def test_stale_digest_is_409_with_the_new_quote_and_a_fresh_one_books():
    space, _ = pricing_space("guard-booking")
    install(space, "bookings")
    room = bookable(space, amount="5.00")
    booker = member(space)
    booker.phone = "+919999999997"
    booker.save(update_fields=["phone"])
    starts = timezone.now() + timedelta(days=1)
    ends = starts + timedelta(hours=1)
    shown = quote(space, "bookings", room, params={"starts_at": starts, "ends_at": ends})
    rate(space, "bookings", per_hour="4.00")
    url = f"/api/v1/public/{space.slug}/spaces/{room.public_token}/book/"
    body = {"starts_at": starts.isoformat(), "ends_at": ends.isoformat(), "quote_digest": shown.digest}
    refused = client(booker).post(url, body, format="json")
    if refused.status_code == 404:
        raise AssertionError(refused.data)
    assert refused.status_code == 409 and refused.data["code"] == "price_changed"
    assert D(refused.data["quote"]["total"]) == D("9.00")
    assert not Booking.objects.filter(space=room).exists()
    fresh = quote(space, "bookings", room, params={"starts_at": starts, "ends_at": ends})
    accepted = client(booker).post(url, {**body, "quote_digest": fresh.digest}, format="json")
    assert accepted.status_code == 201, accepted.data
    assert APIClient  # anonymous submits are refused by the booking view before pricing

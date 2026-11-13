"""Final audit 0.12.0 (M10), decision 223(m): two pending event holds on one slot must not block
each other's approval. First request wins: a booking being admitted is blocked only by holds
with a lower id."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.bookings.models import Booking
from apps.bookings.services_schedule import confirmed_overlap
from tests.bookings.admin_api_helpers import booking, space, tenant

pytestmark = pytest.mark.django_db


def test_pending_holds_on_the_same_slot_only_block_later_requests(monkeypatch):
    room = space(tenant("f1-holds"))
    start = timezone.now() + timedelta(days=2)
    first = booking(room, starts_at=start, status=Booking.Status.PENDING)
    second = booking(room, starts_at=start, status=Booking.Status.PENDING)
    monkeypatch.setattr("apps.bookings.event_holds.tentative_booking_ids", lambda *a, **k: [first.pk, second.pk])
    ends = start + timedelta(hours=1)
    assert confirmed_overlap(room, start, ends, exclude=first.pk) is False  # the earlier request can be approved
    assert confirmed_overlap(room, start, ends, exclude=second.pk) is True  # the later one waits for the first
    assert confirmed_overlap(room, start, ends) is True  # a stranger is still blocked by either hold

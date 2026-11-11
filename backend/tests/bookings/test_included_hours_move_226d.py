"""Decision 226(d): a booking move releases and re-takes its included hours for the new time.

Written, not run: the consolidation lane runs it with the isolated Docker stack.
"""
import pytest

from apps.bookings.included_hours_ledger import live_consumption, used_minutes
from apps.bookings.models_included_hours import IncludedHoursUsage
from apps.bookings.services_staff_edit import edit_booking_time
from apps.payments.pricing.errors import PriceChanged
from tests.bookings.test_included_hours_221d import book, slot, world

pytestmark = pytest.mark.django_db


def _tools(maker):
    """edit_booking_time is a staff-tools surface: the space needs `bookings.staff_tools`."""
    maker.enabled_features = sorted(set(maker.enabled_features or []) | {"bookings.staff_tools"})
    maker.save(update_fields=["enabled_features"])


def test_a_shorter_move_gives_hours_back_and_retakes_only_the_new_minutes():
    maker, staff, member, room, term, _ = world("mv-short", hours=3)
    _tools(maker)
    booking = book(room, member, day=1, hours=2)
    start, end = slot(3, 1)
    edit_booking_time(booking, actor=staff, starts_at=start, ends_at=end)
    assert live_consumption(booking).minutes == 60 and used_minutes(term, "booking") == 60
    assert IncludedHoursUsage.objects.filter(booking=booking, entry="reverse").count() == 1


def test_a_move_that_needs_more_included_hours_goes_to_price_confirmation_and_rolls_back():
    maker, staff, member, room, term, _ = world("mv-grow", hours=3)
    _tools(maker)
    booking = book(room, member, day=1, hours=1)
    start, end = slot(3, 3)
    with pytest.raises(PriceChanged) as changed:
        edit_booking_time(booking, actor=staff, starts_at=start, ends_at=end)
    assert live_consumption(booking).minutes == 60 and used_minutes(term, "booking") == 60  # untouched
    digest = changed.value.detail["confirmation"]["price_confirmation"]
    edit_booking_time(booking, actor=staff, starts_at=start, ends_at=end, price_confirmation=digest)
    assert live_consumption(booking).minutes == 180

"""Decision 246 (lane F8): validation and audit conditions for plan included hours (221d)."""
import pytest
from rest_framework import serializers

from apps.admin_api.serializers_membership_plans import MembershipPlanSerializer
from apps.audit.models import AuditLog
from apps.bookings.included_hours_ledger import release
from apps.bookings.services_bookings import approve_booking, reject_booking
from apps.bookings.services_transitions import cancel_booking
from tests.bookings.test_included_hours_221d import book, world

pytestmark = pytest.mark.django_db

FIELDS = ("included_booking_hours", "included_machine_hours")


@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("bad", [-1, 8785, "abc", 1.5, None])
def test_included_hours_fields_refuse_negative_oversized_or_non_integer_values(field, bad):
    with pytest.raises(serializers.ValidationError):
        MembershipPlanSerializer().fields[field].run_validation(bad)


@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize("good", [0, 1, 8784])
def test_included_hours_fields_accept_the_whole_valid_range(field, good):
    assert MembershipPlanSerializer().fields[field].run_validation(good) == good


def _count(maker, action):
    return AuditLog.objects.filter(makerspace=maker, action=action).count()


def test_consuming_hours_writes_one_audit_row_naming_the_minutes():
    maker, _, member, room, _, _ = world("f8-221d-aud")
    booking = book(room, member, hours=2)
    row = AuditLog.objects.get(makerspace=maker, action="booking.included_hours_consumed")
    assert row.meta["booking_id"] == booking.pk and row.meta["minutes"] == 120 and row.meta["kind"] == "booking"
    assert _count(maker, "booking.included_hours_restored") == 0


def test_a_fully_priced_booking_with_no_hours_left_writes_no_consume_audit():
    maker, _, member, room, _, _ = world("f8-221d-none", hours=0)
    book(room, member, hours=1)
    assert _count(maker, "booking.included_hours_consumed") == 0


def test_cancel_and_reject_each_restore_once_and_a_replay_adds_no_audit_row():
    maker, staff, member, room, _, _ = world("f8-221d-restore", approval="approve")
    pending = book(room, member, hours=2)
    reject_booking(pending, actor=staff, reason="no")
    assert _count(maker, "booking.included_hours_restored") == 1
    assert release(pending, staff) is None
    assert _count(maker, "booking.included_hours_restored") == 1
    again = book(room, member, day=2, hours=1)
    approve_booking(again, actor=staff)
    cancel_booking(again, actor=staff)
    assert _count(maker, "booking.included_hours_restored") == 2
    assert _count(maker, "booking.included_hours_consumed") == 2


def test_audit_rows_stay_in_their_own_space():
    maker, _, member, room, _, _ = world("f8-221d-own")
    other, _, other_member, other_room, _, _ = world("f8-221d-other")
    book(room, member, hours=2)
    assert _count(other, "booking.included_hours_consumed") == 0
    book(other_room, other_member, hours=1)
    assert _count(maker, "booking.included_hours_consumed") == 1

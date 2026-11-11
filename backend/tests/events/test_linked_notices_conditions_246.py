"""Decision 246 (lane T4): service-level conditions for the linked-booking organizer notice (221f).

Calls `linked_booking_notices.notify_organizers` and `staff_eligible` directly: a replay of the same
booking revision creates no second envelope, a new revision does, an unknown change is refused,
the notice stays silent with Events or Bookings off, and nobody from another space is a recipient.
"""
import pytest

from apps.bookings.models import Booking
from apps.events import linked_booking_notices as notices
from apps.integrations.models_contract import NotificationEnvelope
from apps.makerspaces.models import Makerspace
from tests.events.test_booking_decision_replacement import linked
from tests.machines.certification_helpers import _member

pytestmark = pytest.mark.django_db(transaction=True)


def envelopes(event):
    return NotificationEnvelope.objects.filter(event=notices.EVENT, source_id=str(event.pk))


def test_a_replay_of_the_same_change_creates_no_second_envelope_but_a_new_revision_does():
    _maker, staff, _member, event, _room, booking, _decision, _client = linked("t246-ln-replay")
    notices.notify_organizers(booking, "moved")
    first = envelopes(event).count()
    assert first > 0 and staff.pk in set(envelopes(event).values_list("recipient_id", flat=True))
    notices.notify_organizers(booking, "moved")
    assert envelopes(event).count() == first
    Booking.objects.filter(pk=booking.pk).update(calendar_sequence=booking.calendar_sequence + 1)
    booking.refresh_from_db()
    notices.notify_organizers(booking, "moved")
    assert envelopes(event).count() == 2 * first


def test_an_unknown_change_word_sends_nothing():
    _maker, _staff, _member, event, _room, booking, _decision, _client = linked("t246-ln-unknown")
    assert notices.notify_organizers(booking, "exploded") is None
    assert not envelopes(event).exists()


@pytest.mark.parametrize("module", ["events", "bookings"])
def test_the_notice_is_silent_when_either_module_is_off(module):
    maker, _staff, _member, event, _room, booking, _decision, _client = linked(f"t246-ln-off-{module}")
    Makerspace.objects.filter(pk=maker.pk).update(
        enabled_modules=sorted(set(maker.enabled_modules or []) - {module}))
    booking.refresh_from_db()
    assert notices.notify_organizers(booking, "cancelled") is None
    assert not envelopes(event).exists()


def test_staff_of_another_space_never_receive_this_spaces_booking_notice():
    maker, _staff, _member, event, _room, booking, _decision, _client = linked("t246-ln-xsp")
    _other_maker, other_staff, _other_member, other_event, _r, _b, _d, _c = linked("t246-ln-xsp-b")
    notices.notify_organizers(booking, "moved")
    heard = set(envelopes(event).values_list("recipient_id", flat=True))
    assert other_staff.pk not in heard
    assert set(envelopes(event).values_list("makerspace_id", flat=True)) == {maker.pk}
    assert not envelopes(other_event).exists()


def test_the_queued_staff_notice_goes_stale_when_bookings_is_switched_off_afterwards():
    maker, staff, _member, event, _room, booking, _decision, _client = linked("t246-ln-stale")
    notices.notify_organizers(booking, "moved")
    row = envelopes(event).filter(recipient=staff, audience="staff").get()
    assert notices.staff_eligible(row)
    Makerspace.objects.filter(pk=maker.pk).update(
        enabled_modules=sorted(set(maker.enabled_modules or []) - {"bookings"}))
    row.refresh_from_db()
    assert not notices.staff_eligible(row)


def test_a_plain_member_of_the_space_is_not_a_recipient():
    maker, _staff, _member_row, event, _room, booking, _decision, _client = linked("t246-ln-plain")
    plain, _ = _member(maker, "t246-ln-plain-user")
    notices.notify_organizers(booking, "moved")
    assert plain.pk not in set(envelopes(event).values_list("recipient_id", flat=True))

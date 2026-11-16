from datetime import timedelta
from uuid import uuid4
import pytest
from django.utils import timezone
from apps.events.contributions import management_workflow
from apps.events.contributions.errors import ProgrammeError
from apps.events.contributions.models import EventRolePosting, EventShift, EventContributorNotice
from apps.events.mentoring import office_hours_workflow, configuration_workflow
from apps.events.mentoring.models import OfficeHoursChange, OfficeHoursBooking
from tests.events.collab_helpers import make_staff
from tests.events.programme.mentoring.helpers import setup_help


@pytest.mark.django_db(transaction=True)
def test_occupied_slot_edit_refuses_then_explicit_reschedule_cancels_and_notifies(settings):
    space, event, users, _, roles, team, _ = setup_help(settings)
    manager = make_staff(space)
    posting = EventRolePosting.objects.create(event=event, makerspace=space, role="mentor", title="Office hours",
        opens_at=event.starts_at, closes_at=event.ends_at)
    slot = EventShift.objects.create(event=event, makerspace=space, posting=posting, kind="office_hours",
        mentor_assignment=roles[0], task="PCB help", capacity=1,
        starts_at=timezone.now() + timedelta(minutes=30), ends_at=timezone.now() + timedelta(minutes=50),
        signup_deadline=timezone.now() + timedelta(minutes=20))
    booking = office_hours_workflow.book(actor=users[0], event_id=event.pk, slot_id=slot.pk,
        payload={"operation_id": uuid4(), "expected_version": slot.version, "team_id": team.pk}).row
    payload = {"operation_id": uuid4(), "expected_version": slot.version,
        "starts_at": slot.starts_at + timedelta(minutes=10), "ends_at": slot.ends_at + timedelta(minutes=10)}
    with pytest.raises(ProgrammeError) as error:
        management_workflow.save_shift(actor=manager, event_id=event.pk, shift_id=slot.pk, payload=payload)
    assert error.value.detail["code"] == "active_bookings"
    result = management_workflow.save_shift(actor=manager, event_id=event.pk, shift_id=slot.pk,
        payload={**payload, "operation_id": uuid4(), "cancel_bookings": True, "reason": "Mentor travel delay"})
    booking.refresh_from_db()
    assert booking.state == "cancelled" and OfficeHoursChange.objects.filter(slot=slot).count() == 1
    assert EventContributorNotice.objects.filter(booking=booking, kind="booking_cancelled").count() == 1
    assert result.row.starts_at == payload["starts_at"]

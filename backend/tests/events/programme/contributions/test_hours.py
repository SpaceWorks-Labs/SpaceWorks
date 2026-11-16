from datetime import datetime, timedelta, timezone
import pytest
from apps.events.contributions.attendance_workflow import counted_minutes
from apps.events.contributions.errors import ProgrammeError
from apps.events.contributions.serializers_management import requirements
from rest_framework.exceptions import ValidationError


def test_overnight_hours_use_elapsed_time_and_bounded_breaks():
    start = datetime(2026, 10, 24, 23, 30, tzinfo=timezone.utc)
    assert counted_minutes(start, start + timedelta(hours=3), 20) == 160


@pytest.mark.parametrize("end_minutes,breaks", [(-1, 0), (10, 11), (10, -1)])
def test_invalid_or_negative_intervals_refused(end_minutes, breaks):
    start = datetime.now(timezone.utc)
    with pytest.raises(ProgrammeError):
        counted_minutes(start, start + timedelta(minutes=end_minutes), breaks)


@pytest.mark.parametrize("key", ["min_age", "max_age", "guardian_consent", "date_of_birth"])
def test_no_age_or_guardian_requirement_can_be_configured(key):
    with pytest.raises(ValidationError):
        requirements({key: 18})


@pytest.mark.django_db
def test_delegated_manager_cannot_verify_own_contribution(settings):
    from uuid import uuid4
    from django.utils import timezone as django_timezone
    from apps.events.models import EventStaffGrant
    from apps.events.contributions.models import (EventGrantEntitlement, EventShiftSignup,
        EventShiftAttendance, EventContributionHours, EventContributionHoursEntry)
    from apps.events.contributions.attendance_workflow import command
    from tests.events.programme.contributions.helpers import setup_shift
    space, event, _, shift, users, roles, adapter = setup_shift(settings)
    grant = EventStaffGrant.objects.create(event=event, makerspace=space, user=users[0],
        granted_by=adapter.issuer, permissions=["manage_volunteers"])
    EventGrantEntitlement.objects.create(event=event, makerspace=space, grant=grant,
        source_kind="manual", permissions=["manage_volunteers"], created_by=adapter.issuer)
    signup = EventShiftSignup.objects.create(event=event, makerspace=space, shift=shift,
        assignment=roles[0], member=users[0], state="approved")
    now = django_timezone.now()
    EventShiftAttendance.objects.create(event=event, makerspace=space, signup=signup,
        state="checked_out", checked_in_at=now - timedelta(hours=1), checked_out_at=now)
    EventContributionHours.objects.create(event=event, makerspace=space, signup=signup, minutes=60)
    with pytest.raises(ProgrammeError) as error:
        command(actor=users[0], event_id=event.pk, signup_id=signup.pk, action="verify_hours",
            payload={"operation_id": uuid4(), "expected_version": signup.version}, staff=True)
    assert error.value.detail["code"] == "self_verification_forbidden"
    assert not EventContributionHoursEntry.objects.exists()

from types import SimpleNamespace
from uuid import uuid4
import pytest
from django.db import transaction
from django.utils import timezone
from apps.events.models import EventRegistration, EventTicketType
from apps.events.contracts.providers import LockedContext
from apps.events.contributions import admission_adapter, certificate_subjects
from apps.events.contributions.errors import ProgrammeError
from apps.events.contributions.models import (EventContributorAdmission, EventShiftSignup,
    EventShiftAttendance, EventContributionHours, EventContributionHoursEntry)
from tests.events.programme.contributions.completion_helpers import role_setup, command


@pytest.mark.django_db(transaction=True)
def test_admission_is_fail_closed_without_a_and_creates_no_synthetic_registration(settings):
    space, event, _, _, _, roles, _, manager = role_setup(settings)
    ticket = EventTicketType.objects.create(event=event, makerspace=space, name="Contributor")
    with pytest.raises(ProgrammeError) as error:
        admission_adapter.admit(actor=manager, event_id=event.pk, assignment_id=roles[0].pk,
            payload=command(roles[0], ticket_type_id=ticket.pk, capacity_policy="event_capacity"))
    assert error.value.status_code == 503
    assert not EventRegistration.objects.exists() and not EventContributorAdmission.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_admission_calls_normal_adapter_with_explicit_capacity_and_subject_fences(settings):
    space, event, _, _, users, roles, adapter, manager = role_setup(settings)
    ticket = EventTicketType.objects.create(event=event, makerspace=space, name="Contributor")
    def admit_locked(**kwargs):
        request = kwargs["request"]
        assert request.capacity_policy == "reserved_contributor_capacity"
        assert users[0].pk in kwargs["locks"].account_ids
        # Test adapter only: A/G production must call normal admission services.
        return EventRegistration.objects.create(event=event, member=users[0], ticket_type=ticket, name="Crew",
            email=users[0].email, phone="12345678").pk
    adapter.admissions = SimpleNamespace(admit_locked=admit_locked)
    payload = command(roles[0], ticket_type_id=ticket.pk, capacity_policy="reserved_contributor_capacity")
    first = admission_adapter.admit(actor=manager, event_id=event.pk, assignment_id=roles[0].pk, payload=payload)
    replay = admission_adapter.admit(actor=manager, event_id=event.pk, assignment_id=roles[0].pk, payload=payload)
    assert first.row.registration_id == replay.row.registration_id and replay.replayed
    assert EventRegistration.objects.count() == EventContributorAdmission.objects.count() == 1


@pytest.mark.django_db
def test_certificate_requires_independent_verified_hours_without_attendance_registration(settings):
    space, event, _, shift, users, roles, _, manager = role_setup(settings)
    locks = LockedContext(event_id=event.pk, tenant_ids=(space.pk,), account_ids=(users[0].pk,))
    with transaction.atomic(), pytest.raises(ProgrammeError):
        certificate_subjects.resolve(event_id=event.pk, assignment_id=roles[0].pk, locks=locks)
    signup = EventShiftSignup.objects.create(event=event, makerspace=space, shift=shift, assignment=roles[0], member=users[0], state="approved")
    EventShiftAttendance.objects.create(event=event, makerspace=space, signup=signup, state="checked_out",
        checked_in_at=event.starts_at, checked_out_at=timezone.now())
    hours = EventContributionHours.objects.create(event=event, makerspace=space, signup=signup, state="verified", minutes=60, version=2)
    EventContributionHoursEntry.objects.create(event=event, makerspace=space, hours=hours, actor=manager,
        previous_version=1, minutes=60, kind="verified")
    with transaction.atomic():
        subject = certificate_subjects.resolve(event_id=event.pk, assignment_id=roles[0].pk, locks=locks)
    assert subject.minutes == 60 and subject.evidence == ((hours.pk, 2),)
    assert not EventRegistration.objects.exists()
    roles[0].imported_inert = True
    roles[0].save(update_fields=["imported_inert"])
    from django.http import Http404
    with transaction.atomic(), pytest.raises(Http404):
        certificate_subjects.resolve(event_id=event.pk, assignment_id=roles[0].pk, locks=locks)

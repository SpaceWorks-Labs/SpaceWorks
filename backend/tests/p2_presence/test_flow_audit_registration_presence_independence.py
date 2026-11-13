"""Flow audit: event registration and presence are two independent facts (docs/INVARIANTS.md, events invariants).

Registering is planning to attend and needs no PresenceSession; the staff-scanned QR check-in is the evidence of
being there. Each direction is pinned with exact rows: registering writes no check-in and no presence; a presence
session (started, ended, expired) writes no registration and never moves one; a live QR check-in marks the
registration attended and, with presence on, creates exactly one bound `attending_event` session; and the two ends
of that pair never rewrite each other afterwards.
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.events import services_registration
from apps.events.models import Event, EventCheckInEvent, EventRegistration
from apps.events.services_checkin import mark_attended_with_event
from apps.presence import services
from apps.presence.models import PresenceSession

pytestmark = pytest.mark.django_db


def _running_event(lane):
    now = timezone.now()
    return Event.objects.create(makerspace=lane.space, title="Open lab night", status="published", is_public=True,
                                starts_at=now - timedelta(hours=1), ends_at=now + timedelta(hours=2),
                                created_by=lane.staff)


def _register(event, member):
    return services_registration.register(event, member=member, name=member.display_name, email=member.email,
                                          phone="1234567890", actor=member)


def test_registering_writes_no_check_in_and_no_presence_session(lane):
    event = _running_event(lane)
    registration = _register(event, lane.owner)
    registration = registration[0] if isinstance(registration, tuple) else registration  # (row, ...) or row
    row = EventRegistration.objects.get(event=event, member=lane.owner)
    assert row.pk == registration.pk and row.status == EventRegistration.Status.REGISTERED
    assert EventCheckInEvent.objects.filter(registration=row).count() == 0
    assert PresenceSession.objects.filter(account=lane.owner).count() == 0


def test_a_presence_session_neither_creates_nor_moves_a_registration(lane):
    event = _running_event(lane)
    registered = EventRegistration.objects.filter(event=event, member=lane.owner)
    assert not registered.exists()  # never registered
    session = services.start_session(lane.owner, lane.space, 60, latitude=0, longitude=0)
    assert session.status == "visiting" and session.event_registration_id is None
    assert EventRegistration.objects.filter(event=event).count() == 0  # presence invented no registration
    services.end_session(lane.owner, lane.space)
    assert EventRegistration.objects.filter(event=event).count() == 0
    assert EventCheckInEvent.objects.filter(event=event).count() == 0


def test_a_live_qr_check_in_attends_the_registration_and_binds_exactly_one_presence_session(
        lane, django_capture_on_commit_callbacks):
    event = _running_event(lane)
    _register(event, lane.owner)
    registration = EventRegistration.objects.get(event=event, member=lane.owner)
    with django_capture_on_commit_callbacks(execute=True):
        updated, check_in = mark_attended_with_event(registration, actor=lane.staff, source="qr")
    assert updated.status == EventRegistration.Status.ATTENDED
    assert EventCheckInEvent.objects.filter(registration=registration).count() == 1
    [session] = PresenceSession.objects.filter(event_registration=registration)
    assert (session.status, session.account_id) == ("attending_event", lane.owner.pk)
    assert session.expires_at <= event.ends_at
    # Ending or expiring the presence session never un-attends the registration or removes the check-in.
    services.end_session(lane.owner, lane.space)
    assert EventRegistration.objects.get(pk=registration.pk).status == EventRegistration.Status.ATTENDED
    assert EventCheckInEvent.objects.filter(registration=registration).count() == 1
    assert PresenceSession.objects.filter(event_registration=registration).count() == 1  # history kept, none added


def test_staff_marking_online_attends_the_registration_but_creates_no_presence(lane, django_capture_on_commit_callbacks):
    event = _running_event(lane)
    _register(event, lane.owner)
    registration = EventRegistration.objects.get(event=event, member=lane.owner)
    with django_capture_on_commit_callbacks(execute=True):
        updated, _ = mark_attended_with_event(registration, actor=lane.staff, source="online")
    assert updated.status == EventRegistration.Status.ATTENDED
    assert not PresenceSession.objects.filter(account=lane.owner).exists()  # a staff mark is not proof of being here

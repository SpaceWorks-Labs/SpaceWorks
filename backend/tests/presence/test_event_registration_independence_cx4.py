"""Registration is a plan; presence is an independent, time-bounded observation."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.events.models import Event, EventCheckInEvent, EventRegistration
from apps.events.services_registration import register
from apps.makerspaces.module_install import install_module, uninstall_module
from apps.presence.models import PresenceSession
from apps.presence.services import end_session, start_session
from tests.p2_presence.conftest import lane, no_external_delivery  # noqa: F401

pytestmark = pytest.mark.django_db


def event_for(space):
    now = timezone.now()
    return Event.objects.create(makerspace=space, title="Community build", status="published", is_public=True,
                                starts_at=now - timedelta(minutes=30), ends_at=now + timedelta(hours=3))


def test_start_end_and_replay_preserve_every_existing_registration_column(lane):  # noqa: F811
    event = event_for(lane.space)
    register(event, member=lane.owner, name="Member", email=lane.owner.email, phone="1234567890", actor=lane.owner)
    before = list(EventRegistration.objects.filter(event=event).values())
    assert len(before) == 1
    assert PresenceSession.objects.filter(makerspace=lane.space).count() == 0
    session = start_session(lane.owner, lane.space, 60, latitude=0, longitude=0)
    assert start_session(lane.owner, lane.space, 60, latitude=0, longitude=0).pk == session.pk
    assert list(EventRegistration.objects.filter(event=event).values()) == before
    end_session(lane.owner, lane.space)
    assert list(EventRegistration.objects.filter(event=event).values()) == before
    assert EventCheckInEvent.objects.filter(event=event).count() == 0
    assert PresenceSession.objects.filter(makerspace=lane.space, account=lane.owner).count() == 1
    assert AuditLog.objects.filter(makerspace=lane.space, action="presence.started").count() == 1
    assert AuditLog.objects.filter(makerspace=lane.space, action="presence.ended").count() == 1


def test_registration_works_with_presence_removed_and_restoring_it_does_not_check_anyone_in(lane):  # noqa: F811
    event = event_for(lane.space)
    uninstall_module(lane.space, "presence")
    register(event, member=lane.owner, name="Member", email=lane.owner.email, phone="1234567890", actor=lane.owner)
    before = list(EventRegistration.objects.filter(event=event).values())
    assert len(before) == 1 and before[0]["status"] == "registered"
    install_module(lane.space, "presence")
    assert list(EventRegistration.objects.filter(event=event).values()) == before
    assert PresenceSession.objects.filter(makerspace=lane.space).count() == 0
    assert EventCheckInEvent.objects.filter(event=event).count() == 0


def test_presence_with_events_removed_and_restored_never_invents_a_registration(lane):  # noqa: F811
    event = event_for(lane.space)
    uninstall_module(lane.space, "events")
    session = start_session(lane.owner, lane.space, 60, latitude=0, longitude=0)
    before = PresenceSession.objects.values().get(pk=session.pk)
    install_module(lane.space, "events")
    assert PresenceSession.objects.values().get(pk=session.pk) == before
    assert EventRegistration.objects.filter(event=event).count() == 0
    assert EventCheckInEvent.objects.filter(event=event).count() == 0

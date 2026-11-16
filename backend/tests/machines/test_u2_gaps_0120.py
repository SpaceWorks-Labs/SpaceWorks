"""Release 0.12.0 UI-lane U2 gaps: supervisee picker, member machine list with ids, machine filter."""
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.events.models import EventRegistration
from apps.machines import supervised
from apps.machines.models import EventInductionLink, Machine
from rest_framework.exceptions import ValidationError
from apps.presence.models import PresenceSession
from tests.events.checkin_helpers import make_event, register
from tests.machines.certification_helpers import _certification, _machine_type, _manager, _member, _space
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db


def _world(slug="u2m"):
    space = _space(slug, modules=("machines", "events"), certifications=False)
    space.enabled_features = sorted(set(space.enabled_features or []) | {"machines.supervised_sessions"})
    space.save(update_fields=["enabled_features"])
    machine_type = _machine_type(space)
    machine = Machine.objects.create(makerspace=space, machine_type=machine_type, name="Laser A", is_public=True)
    instructor, _ = _manager(space, f"{slug}-inst", machine_type)
    return space, machine, instructor


def _named(space, username, display_name):
    user, _ = _member(space, username)
    user.display_name = display_name
    user.save(update_fields=["display_name"])
    return user


def _present(space, user):
    now = timezone.now()
    PresenceSession.objects.create(member=user, account=user, makerspace=space, status="visiting",
                                   started_at=now - timedelta(minutes=5), expires_at=now + timedelta(hours=1))


def _picker(client, session, q):
    return client.get(reverse("member-supervised-people", kwargs={"pk": session.pk}), {"q": q})


def test_picker_finds_only_checked_in_or_event_registered_people_with_two_characters():
    cache.clear()
    space, machine, instructor = _world()
    here = _named(space, "u2m-here", "Zelda Present")
    _named(space, "u2m-away", "Zelda Absent")
    _present(space, here)
    event = make_event(space)
    registered = _named(space, "u2m-reg", "Zelda Registered")
    register(event, registered, status=EventRegistration.Status.REGISTERED)
    # A bound event must be one the instructor runs or an induction for this machine type (API scoping audit).
    with pytest.raises(ValidationError):
        supervised.open_session(machine, instructor, event=event)
    EventInductionLink.objects.create(makerspace=space, event=event,
                                      certification_type=_certification(space, machine.machine_type))
    session = supervised.open_session(machine, instructor, event=event)
    client = authenticated_client(instructor)
    names = {row["display_name"] for row in _picker(client, session, "Zel").json()["results"]}
    assert names == {"Zelda Present", "Zelda Registered"}
    row = _picker(client, session, "Zelda Pre").json()["results"][0]
    assert set(row) == {"id", "display_name"}
    assert _picker(client, session, "Z").status_code == 400


def test_picker_is_for_the_instructor_of_an_open_session_only():
    cache.clear()
    space, machine, instructor = _world("u2m2")
    other, _ = _member(space, "u2m2-other")
    session = supervised.open_session(machine, instructor)
    assert _picker(authenticated_client(other), session, "ab").status_code == 404
    supervised.close_session(session, actor=instructor)
    assert _picker(authenticated_client(instructor), session, "ab").status_code == 404


def test_member_machine_list_carries_ids_for_members_only():
    space, machine, _ = _world("u2m3")
    member, _ = _member(space, "u2m3-member")
    url = reverse("member-machines", kwargs={"makerspace_id": space.pk})
    assert authenticated_client(member).get(url).json()["results"][0]["id"] == machine.pk
    outsider = User.objects.create_user("u2m3-out", email="o@e.com", access_status="active")
    assert authenticated_client(outsider).get(url).status_code == 403


def test_supervised_session_list_filters_by_machine_and_rejects_junk():
    space, machine, instructor = _world("u2m4")
    second = Machine.objects.create(makerspace=space, machine_type=machine.machine_type, name="Laser B")
    supervised.open_session(machine, instructor)
    supervised.open_session(second, instructor)
    client = authenticated_client(instructor)
    url = reverse("member-supervised-sessions", kwargs={"makerspace_id": space.pk})
    rows = client.get(url, {"machine": machine.pk}).json()["results"]
    assert [row["machine"] for row in rows] == [machine.pk]
    assert client.get(url, {"machine": "abc"}).status_code == 400

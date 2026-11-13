"""Open items A22 (EB6): the cross-event queue of registrations waiting on staff."""
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.events.models import Event, EventRegistration
from tests.events.collab_helpers import client_for
from tests.events.manual_grant_fixture import create_manual_grant
from tests.events.orders_helpers import l6_space, make_staff, verified

pytestmark = pytest.mark.django_db


def _event(space, title, *, days=2, capacity=1, **values):
    starts = timezone.now() + timedelta(days=days)
    return Event.objects.create(makerspace=space, title=title, starts_at=starts, ends_at=starts + timedelta(hours=2),
                                registration_audience="accounts", is_public=True, status="published", capacity=capacity, **values)


def _registration(event, name, status):
    return EventRegistration.objects.create(event=event, name=name, email=f"{name}@example.test", phone="",
                                            status=status)


def _url(space):
    return reverse("admin-event-registration-queue", kwargs={"makerspace_id": space.pk})


def test_manager_sees_pending_and_waitlisted_rows_across_upcoming_events_only():
    space = l6_space("queue-a22")
    manager = make_staff(space, "queue-mgr")
    first, second = _event(space, "Soldering"), _event(space, "Laser basics", days=3)
    past = _event(space, "Old meetup", days=-3)
    pending = _registration(first, "ana", "pending_approval")
    waiting = _registration(second, "ben", "waitlisted")
    _registration(first, "cy", "registered")
    _registration(past, "dee", "pending_approval")
    response = client_for(manager).get(_url(space))
    assert response.status_code == 200
    rows = response.json()["results"]
    assert [row["id"] for row in rows] == [pending.pk, waiting.pk]
    assert rows[0]["event"]["title"] == "Soldering" and rows[1]["status"] == "waitlisted"
    assert set(rows[0]) == {"id", "status", "created_at", "name", "event"}
    only_waitlist = client_for(manager).get(_url(space), {"status": "waitlisted"}).json()["results"]
    assert [row["id"] for row in only_waitlist] == [waiting.pk]
    one_event = client_for(manager).get(_url(space), {"event": first.pk}).json()["results"]
    assert [row["id"] for row in one_event] == [pending.pk]


def test_grant_holder_sees_only_events_they_manage_registrations_on():
    space = l6_space("queue-grant")
    granted, other = _event(space, "Granted"), _event(space, "Not granted")
    holder = verified("queue-holder")
    create_manual_grant(event=granted, makerspace=space, user=holder, permissions=["manage_registrations"])
    mine = _registration(granted, "eve", "pending_approval")
    _registration(other, "fay", "pending_approval")
    rows = client_for(holder).get(_url(space)).json()["results"]
    assert [row["id"] for row in rows] == [mine.pk]


def test_stranger_and_foreign_space_staff_get_404_and_read_writes_no_audit():
    space = l6_space("queue-404")
    _registration(_event(space, "Private"), "gil", "pending_approval")
    stranger = verified("queue-stranger")
    assert client_for(stranger).get(_url(space)).status_code == 404
    foreign = l6_space("queue-foreign")
    foreign_manager = make_staff(foreign, "queue-foreign-mgr")
    assert client_for(foreign_manager).get(_url(space)).status_code == 404
    before = AuditLog.objects.count()
    client_for(make_staff(space, "queue-reader")).get(_url(space))
    assert AuditLog.objects.count() == before


def test_events_module_off_hides_the_queue():
    space = l6_space("queue-off")
    manager = make_staff(space, "queue-off-mgr")
    _registration(_event(space, "Off"), "hal", "pending_approval")
    space.enabled_modules = [module for module in space.enabled_modules if module != "events"]
    space.save(update_fields=["enabled_modules"])
    assert client_for(manager).get(_url(space)).status_code == 404


def test_approving_from_the_queue_uses_the_audited_registration_route():
    space = l6_space("queue-approve")
    manager = make_staff(space, "queue-approve-mgr")
    row = _registration(_event(space, "Approve me", capacity=5, registration_requires_approval=True), "ivy", "pending_approval")
    response = client_for(manager).post(reverse("admin-event-registration-approve", kwargs={"pk": row.pk}), {}, format="json")
    assert response.status_code == 200, response.data
    assert AuditLog.objects.filter(action__startswith="event.registration").exists()
    assert client_for(manager).get(_url(space)).json()["results"] == []

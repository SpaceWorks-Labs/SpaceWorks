"""L1 G3 + X1: online/hybrid delivery, the join-link release rule and the venue map link."""

import pytest
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.events.models import Event, EventRegistration
from apps.events.online_delivery import join_url_for, map_url
from apps.events.services_calendar import render_member_calendar
from tests.events.collab_helpers import client_for, make_member, make_staff
from tests.events.ticketing_helpers import event_space, open_event, public_url

pytestmark = pytest.mark.django_db(transaction=True)
LINK = "https://meet.example.test/room-42?pwd=s3cret"


def fixture(*, on=True, mode="online"):
    space = event_space("online")
    if on:
        space.enabled_features += ["events.online_delivery"]
        space.save(update_fields=["enabled_features"])
    staff = make_staff(space)
    event = open_event(space)
    if on:
        response = client_for(staff).patch(f"/api/v1/admin/events/{event.pk}/",
                                           {"delivery_mode": mode, "join_url": LINK}, format="json")
        assert response.status_code == 200, response.data
    event.refresh_from_db()
    return space, staff, event


def registration(event, status=EventRegistration.Status.REGISTERED):
    member = make_member(event.makerspace, username=f"m{status}")
    return EventRegistration.objects.create(event=event, member=member, name="M", email="m@example.test",
                                            status=status)


def test_join_link_is_encrypted_at_rest_audited_without_the_link_and_shown_to_editors_only():
    _space, staff, event = fixture()
    assert event.delivery_mode == "online" and LINK not in event.join_url_encrypted
    detail = client_for(staff).get(f"/api/v1/admin/events/{event.pk}/").data
    assert detail["join_url"] == LINK and detail["join_url_set"] is True
    row = AuditLog.objects.get(action="event.delivery_mode_changed")
    assert row.meta["new_mode"] == "online" and LINK not in str(row.meta)


def test_join_link_must_be_https_without_credentials():
    _space, staff, event = fixture()
    for bad in ("http://meet.example.test/x", "https://user:pw@meet.example.test/", "javascript:alert(1)"):
        response = client_for(staff).patch(f"/api/v1/admin/events/{event.pk}/", {"join_url": bad}, format="json")
        assert response.status_code == 400, bad


def test_join_link_never_reaches_public_surfaces():
    space, _staff, event = fixture()
    client = APIClient()
    for route in (public_url(event, "public-event-detail"), f"/api/v1/public/{space.slug}/events/",
                  f"/api/v1/public/event-codes/{event.public_token}/", public_url(event, "public-event-calendar"),
                  f"/share/events/{event.public_token}/"):
        response = client.get(route)
        assert LINK not in response.content.decode(), route
    assert client.get(public_url(event, "public-event-detail")).data["delivery_mode"] == "online"


@pytest.mark.parametrize("status,released", [
    (EventRegistration.Status.REGISTERED, True), (EventRegistration.Status.ATTENDED, True),
    (EventRegistration.Status.WAITLISTED, False), (EventRegistration.Status.PENDING_APPROVAL, False),
    (EventRegistration.Status.CANCELLED, False),
])
def test_only_confirmed_registrants_receive_the_link(status, released):
    _space, _staff, event = fixture()
    row = registration(event, status)
    assert (join_url_for(row) == LINK) is released
    calendar = render_member_calendar(event.makerspace, EventRegistration.objects.filter(pk=row.pk)).decode()
    assert ("meet.example.test" in calendar.replace("\r\n ", "")) is released


def test_member_ticket_carries_join_and_map_links():
    space, _staff, event = fixture(mode="hybrid")
    event.location = "Main hall"
    event.save(update_fields=["location"])
    row = registration(event)
    from django.urls import reverse
    ticket = client_for(row.member).get(reverse("member-event-ticket", kwargs={"makerspace_id": space.pk, "pk": row.pk}))
    assert ticket.status_code == 200, ticket.data
    assert ticket.data["map_url"]
    assert ticket.data["join_url"] == LINK and ticket.data["delivery_mode"] == "hybrid"


def test_switch_off_hides_the_link_and_refuses_writes_but_keeps_the_data():
    space, staff, event = fixture()
    row = registration(event)
    space.enabled_features.remove("events.online_delivery")
    space.save(update_fields=["enabled_features"])
    event.refresh_from_db()
    assert join_url_for(row) is None and event.join_url_encrypted
    assert APIClient().get(public_url(event, "public-event-detail")).data["delivery_mode"] is None
    response = client_for(staff).patch(f"/api/v1/admin/events/{event.pk}/", {"delivery_mode": "hybrid"}, format="json")
    assert response.status_code == 404


def test_map_link_for_in_person_and_hybrid_never_online():
    space = event_space("maps")
    space.enabled_features += ["events.online_delivery"]
    space.location = "Kochi"
    space.save(update_fields=["enabled_features", "location"])
    event = open_event(space, location="Electronics bay")
    assert "Electronics%20bay%2C%20Kochi" in map_url(event)
    event.delivery_mode = Event.DeliveryMode.ONLINE
    assert map_url(event) is None
    event.delivery_mode = Event.DeliveryMode.HYBRID
    space.map_url = "https://maps.example.test/space"
    assert map_url(event) == "https://maps.example.test/space"

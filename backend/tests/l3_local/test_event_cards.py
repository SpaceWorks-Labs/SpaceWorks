"""L3 event ID cards (`events.id_cards`, #128, Q-I6/Q-I8/Q-I9, SPEC §4.4) and the door scan."""
import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.card_designs import designs, resolution, tokens
from apps.card_designs.holders import spec_for
from apps.events import id_cards
from apps.events.models import Event, EventIdCard, EventRegistration
from tests.l3_local.helpers import card_space, client, custom_staff, manager, member

pytestmark = pytest.mark.django_db


def _event(slug, *, features=("events.id_cards",)):
    space = card_space(slug, features=features)
    now = timezone.now()
    event = Event.objects.create(makerspace=space, title="Build Night", starts_at=now - timezone.timedelta(hours=1),
                                 ends_at=now + timezone.timedelta(hours=3), status="published")
    return space, event


def _registration(space, event, name="attendee"):
    user, _m = member(space, name)
    return user, EventRegistration.objects.create(event=event, member=user, name=user.username, email=user.email,
                                                  status=EventRegistration.Status.REGISTERED)


def test_cards_issue_only_after_a_design_is_published_and_expire_a_day_after_the_end():
    space, event = _event("ec-issue")
    sm = manager(space)
    user, registration = _registration(space, event)
    assert id_cards.reconcile_event(event.pk) == (0, 0)
    design, _ = resolution.get_or_create(space, "event_card", actor=sm, event=event)
    designs.publish(sm, design)
    assert id_cards.reconcile_event(event.pk) == (1, 0)
    card = EventIdCard.objects.get(registration=registration)
    assert card.valid_until == event.ends_at + timezone.timedelta(days=1)
    assert spec_for("event_card").standing(card) == "valid" and tokens.live("event_card", card)
    assert id_cards.reconcile_event(event.pk) == (0, 0)
    EventRegistration.objects.filter(pk=registration.pk).update(status=EventRegistration.Status.CANCELLED)
    assert id_cards.reconcile_event(event.pk) == (0, 1)
    card.refresh_from_db()
    assert card.status == "revoked" and spec_for("event_card").standing(card) == "revoked"


def test_every_organiser_publishes_without_approval_and_check_in_only_staff_cannot():
    space, event = _event("ec-organisers")
    sm = manager(space)
    event_manager = custom_staff(space, ["event_manager"], "eventmgr")
    design, _ = resolution.get_or_create(space, "event_card", actor=sm, event=event)
    response = client(event_manager).post(f"/api/v1/admin/card-designs/{design.pk}/publish")
    assert response.status_code == 200, response.content
    assert AuditLog.objects.filter(action="card_design.published").exists()
    door = custom_staff(space, ["handover"], "door")
    assert client(door).get(f"/api/v1/admin/card-designs/{design.pk}").status_code == 404
    assert client(door).get(f"/api/v1/admin/events/{event.pk}/id-cards").status_code in (403, 404)


def test_event_designs_api_and_card_list_revoke_role():
    space, event = _event("ec-api", features=("events.id_cards", "events.ticket_designs"))
    sm = manager(space)
    api = client(sm)
    designs_payload = api.get(f"/api/v1/admin/events/{event.pk}/card-designs").json()
    assert set(designs_payload) == {"event_card", "event_ticket"}
    _user, registration = _registration(space, event)
    assert api.post(f"/api/v1/admin/events/{event.pk}/id-cards").status_code == 400
    designs.publish(sm, resolution.get_or_create(space, "event_card", event=event)[0])
    assert api.post(f"/api/v1/admin/events/{event.pk}/id-cards").json()["issued"] == 1
    card = EventIdCard.objects.get(registration=registration)
    assert api.patch(f"/api/v1/admin/event-id-cards/{card.pk}", {"role": "mentor"}, format="json").json()["role"] == "mentor"
    assert api.post(f"/api/v1/admin/event-id-cards/{card.pk}/revoke", {}, format="json").status_code == 400
    revoked = api.post(f"/api/v1/admin/event-id-cards/{card.pk}/revoke", {"reason": "Left"}, format="json")
    assert revoked.json()["status"] == "revoked"


def test_capability_off_hides_event_cards():
    space, event = _event("ec-off", features=())
    sm = manager(space)
    assert client(sm).get(f"/api/v1/admin/events/{event.pk}/id-cards").status_code == 404


def test_door_scan_finds_the_registration_and_checks_in():
    space, event = _event("ec-door")
    sm = manager(space)
    user, registration = _registration(space, event)
    designs.publish(sm, resolution.get_or_create(space, "event_card", event=event)[0])
    id_cards.reconcile_event(event.pk)
    card = EventIdCard.objects.get(registration=registration)
    payload = tokens.url(tokens.live("event_card", card).token)
    response = client(sm).post(f"/api/v1/admin/events/{event.pk}/check-in/card-scan", {"payload": payload},
                               format="json")
    assert response.status_code == 200, response.content
    assert response.json()["registrations"][0]["confirmable"] is True
    checked = client(sm).post(f"/api/v1/admin/events/{event.pk}/check-in/card-scan",
                              {"payload": payload, "check_in": True}, format="json")
    assert checked.status_code == 200, checked.content
    registration.refresh_from_db()
    assert registration.status == EventRegistration.Status.ATTENDED
    body = checked.json()
    assert body["checked_in"] == registration.pk
    assert body["registrations"][0]["status"] == EventRegistration.Status.ATTENDED
    assert body["registrations"][0]["confirmable"] is False
    assert client(sm).post(f"/api/v1/admin/events/{event.pk}/check-in/card-scan", {"payload": "nope"},
                           format="json").status_code == 404


def test_first_aid_extras_only_behind_the_event_switch():
    from apps.card_designs import extras
    space, event = _event("ec-extras")
    sm = manager(space)
    user, registration = _registration(space, event)
    designs.publish(sm, resolution.get_or_create(space, "event_card", event=event)[0])
    id_cards.reconcile_event(event.pk)
    card = EventIdCard.objects.get(registration=registration)
    extras.write(user, "event_card", card, opted_in=True, blood_group="A+")
    api = client(sm)
    assert api.get(f"/api/v1/admin/events/{event.pk}/id-cards/extras").status_code == 404
    api.put(f"/api/v1/admin/events/{event.pk}/card-settings", {"extras_visible_to_organizers": True}, format="json")
    rows = api.get(f"/api/v1/admin/events/{event.pk}/id-cards/extras").json()
    assert rows[0]["blood_group"] == "A+"
    assert AuditLog.objects.filter(action="event_card.extras_viewed").exists()

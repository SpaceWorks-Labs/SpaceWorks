"""SYNC-1: GET admin/events/<pk>/card-designs?ticket_type=X creates only the ticket design it was asked for."""
import pytest
from django.utils import timezone

from apps.card_designs.models import CardDesign
from apps.events.models import Event, EventTicketType
from tests.l3_local.helpers import card_space, client, manager

pytestmark = pytest.mark.django_db


def _event(slug):
    space = card_space(slug, features=("events.id_cards", "events.ticket_designs", "events.ticket_types"))
    now = timezone.now()
    event = Event.objects.create(makerspace=space, title="Build Night", starts_at=now + timezone.timedelta(days=1),
                                 ends_at=now + timezone.timedelta(days=1, hours=3), status="published")
    ticket_type = EventTicketType.objects.create(makerspace=space, event=event, name="Early bird")
    return space, event, ticket_type


def test_ticket_type_request_creates_only_the_ticket_design_for_that_type():
    space, event, ticket_type = _event("s1-tt")
    api = client(manager(space))
    response = api.get(f"/api/v1/admin/events/{event.pk}/card-designs?ticket_type={ticket_type.pk}")
    assert response.status_code == 200, response.content
    assert set(response.json()) == {"event_ticket"}
    rows = CardDesign.objects.filter(ticket_type=ticket_type)
    assert [row.domain for row in rows] == ["event_ticket"]
    assert not CardDesign.objects.filter(event=event, domain="event_card").exists()


def test_plain_request_still_returns_both_event_designs_without_ticket_type_rows():
    space, event, ticket_type = _event("s1-plain")
    api = client(manager(space))
    payload = api.get(f"/api/v1/admin/events/{event.pk}/card-designs").json()
    assert set(payload) == {"event_card", "event_ticket"}
    assert not CardDesign.objects.filter(ticket_type=ticket_type).exists()

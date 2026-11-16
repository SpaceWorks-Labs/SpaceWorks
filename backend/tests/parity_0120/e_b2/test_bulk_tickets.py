"""Bulk status sets, the one-card-per-page layout, the desk's provisional badges, and the D17 ticket rules."""
import pytest
from rest_framework.exceptions import ValidationError

from apps.card_designs import sheets
from apps.events.badge_desk import desk_payload
from apps.events.id_cards_preview import event_card_ids
from apps.events.id_cards_tickets import TicketUsed, merge_values, render_ticket
from apps.events.models import EventRegistration
from tests.l3_local.helpers import client
from tests.parity_0120.e_b2.helpers import FEATURES, issue_cards, live_event, publish_badge, register

pytestmark = pytest.mark.django_db


def _event(slug):
    space, event, sm = live_event(slug)
    publish_badge(space, event, sm)
    return space, event, sm


def test_status_sets_pick_the_right_cards():
    space, event, _sm = _event("e2-sets")
    _a, plain = register(space, event, "plain")
    _b, crew = register(space, event, "crew")
    _c, done = register(space, event, "done")
    EventRegistration.objects.filter(pk=crew.pk).update(is_crew=True)
    EventRegistration.objects.filter(pk=done.pk).update(status="attended")
    cards = issue_cards(event)

    def ids(**values):
        return set(event_card_ids(event, values))

    assert ids(status_set="crew") == {cards[crew.pk].pk}
    assert ids(status_set="attendees_without_crew") == {cards[plain.pk].pk, cards[done.pk].pk}
    assert ids(status_set="checked_in") == {cards[done.pk].pk}
    assert ids(status_set="not_checked_in") == {cards[plain.pk].pk, cards[crew.pk].pk}
    assert ids(status_set="all") == {card.pk for card in cards.values()}
    with pytest.raises(ValidationError):
        ids(status_set="role")


def test_the_per_card_layout_is_one_page_per_card_with_no_sheet_grid():
    assert sheets.grid("per_card", 105.0, 148.0) == (1, 1, 0.0, 0.0)


def test_the_desk_lists_provisional_badges_for_waitlisted_and_pending_people_with_status_set_all():
    space, event, _sm = _event("e2-provisional")
    _u, confirmed = register(space, event, "ok")
    _w, waiting = register(space, event, "wait")
    EventRegistration.objects.filter(pk=waiting.pk).update(status="waitlisted")
    issue_cards(event)
    payload = desk_payload(event, status_set="all")
    by_id = {row["registration_id"]: row for row in payload["badges"]}
    assert by_id[waiting.pk]["provisional"] is True and by_id[confirmed.pk]["provisional"] is False
    assert {row["registration_id"] for row in desk_payload(event, status_set="confirmed")["badges"]} == {confirmed.pk}


def test_the_desk_route_returns_one_badge_row_for_a_registration():
    space, event, sm = _event("e2-desk")
    _u, registration = register(space, event, "ada")
    issue_cards(event)
    body = client(sm).get(f"/api/v1/admin/events/{event.pk}/badges/desk?registration_id={registration.pk}").json()
    assert body["badge"]["registration_id"] == registration.pk and "attendee" in body["roles"]


def test_ticket_merge_fields_and_the_ticket_is_withdrawn_after_check_in():
    space, event, _sm = live_event("e2-ticket", (*FEATURES, "events.ticket_designs"))
    event.location = "Main hall"
    event.save(update_fields=["location"])
    _u, registration = register(space, event, "ada")
    values = merge_values(registration)
    assert values["venue"] == "Main hall" and values["date"] and "–" in values["time"]
    assert set(values) == {"date", "time", "venue", "price", "order", "team"}
    EventRegistration.objects.filter(pk=registration.pk).update(status="attended")
    registration.refresh_from_db()
    with pytest.raises(TicketUsed) as used:
        render_ticket(registration)
    assert used.value.status_code == 410 and used.value.get_codes() == "ticket_used"

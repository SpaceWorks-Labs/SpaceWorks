import pytest
from rest_framework.exceptions import ValidationError

from apps.events.capacity import ticket_spots_left
from apps.events.models import EventTicketType
from apps.events.ticketing_edit import update_ticket
from tests.p2_events.helpers import account, event, make_staff, registration, space

pytestmark = pytest.mark.django_db


def test_waitlist_and_pending_approval_do_not_occupy_ticket_seats():
    home = space("review-ticket-capacity")
    row, actor = event(home), make_staff(home)
    ticket = EventTicketType.objects.create(makerspace=home, event=row, name="General", capacity=10)
    for index, status in enumerate(["registered"] * 9 + ["attended"] + ["waitlisted"] * 20 + ["pending_approval"]):
        entry = registration(row, account(f"capacity-{index}"), status=status)
        entry.ticket_type = ticket
        entry.save(update_fields=["ticket_type"])
    ticket = update_ticket(ticket, actor=actor, capacity=20)
    assert ticket.capacity == 20 and ticket_spots_left(row, ticket) == 10
    ticket = update_ticket(ticket, actor=actor, capacity=10)
    assert ticket.capacity == 10 and ticket_spots_left(row, ticket) == 0
    with pytest.raises(ValidationError):
        update_ticket(ticket, actor=actor, capacity=9)
    assert update_ticket(ticket, actor=actor, capacity=0).capacity == 0

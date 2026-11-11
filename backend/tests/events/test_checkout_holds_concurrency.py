"""L6 G28: two buyers racing for the last seats in two sessions never oversell."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.db import close_old_connections

from apps.events.models import EventCheckoutHold
from tests.events.orders_helpers import place, ticketed_event, verified

pytestmark = pytest.mark.django_db(transaction=True)


def test_concurrent_holds_have_one_winner():
    space, event, _staff, ticket = ticketed_event(amount=10, capacity=2)
    buyers = [verified("first"), verified("second")]
    barrier = Barrier(2)

    def buy(user):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            return place(user, event, [{"ticket_type_id": ticket.pk, "quantity": 2}]).status_code
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(buy, buyers))
    assert sorted(statuses) == [201, 409]
    assert sum(hold.seats for hold in EventCheckoutHold.objects.filter(event=event)) == 2

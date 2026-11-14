"""One retained personal token, with connected booking content hidden/restored independently."""
from datetime import timedelta

import pytest
from tests.modules.test_switch_matrix_objects_rest_isolation import cx11b_isolated_phase  # noqa: F401
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.bookings.models import Booking
from apps.events.calendar_feed_tokens import issue_or_rotate
from tests.inventory.switch_support_cx11b_p1 import prove_route
from tests.modules.switch_matrix_object_helpers import object_world, retained, response_pair
from tests.modules.test_switch_matrix_objects_rest_support import no_domain_writes, switch

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_bookings, pytest.mark.area_events]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
def test_combined_feed_switch_keeps_token_and_restores_the_same_booking(native):
    space, client, objects = object_world(native)
    actor = User.objects.get(username="sx-real-object-manager")
    actor.email = "p1-calendar@example.test"
    actor.save(update_fields=["email"])
    now = timezone.now()
    booking = Booking.objects.create(space=objects["room"], member=actor, name="Retained booker",
        email=actor.email, starts_at=now + timedelta(days=2), ends_at=now + timedelta(days=2, hours=1), status="confirmed")
    feed, token = issue_or_rotate(space, actor, "combined")
    objects.update(booking=booking, feed=feed)
    url = reverse("public-combined-calendar-feed", kwargs={"makerspace_slug": space.slug, "raw_token": token})
    prove_route(space, client, objects, "calendar.combined_feed", lambda c: c.get(url), off=(404, "not_found"),
                check=lambda r: _contains_booking(r, booking))
    before = retained(objects)
    original = switch(space, "bookings")
    with no_domain_writes():
        response = client.get(url)
    assert response_pair(response) == (200, None)
    assert str(booking.public_token).encode() not in response.content
    switch(space, "bookings", original=original)
    response = client.get(url)
    assert response_pair(response) == (200, None)
    _contains_booking(response, booking)
    assert retained(objects) == before


def _contains_booking(response, booking):
    assert str(booking.public_token).encode() in response.content

pytestmark = ([pytestmark] if not isinstance(pytestmark, list) else pytestmark) + [
    pytest.mark.usefixtures("cx11b_isolated_phase")]

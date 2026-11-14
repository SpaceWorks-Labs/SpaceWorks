"""CX11B: released booking embeds retain their page and answer a uniform hidden 404."""
import pytest
from datetime import timedelta
from urllib.parse import urlsplit
from django.urls import reverse
from django.utils import timezone

from apps.bookings.models_website import BookingResourcePageSection
from tests.modules.switch_matrix_object_helpers import object_world, response_pair
from tests.modules.test_switch_matrix_objects_rest_support import no_domain_writes, domain_rows, switch

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("native", [False, True])
@pytest.mark.parametrize("key", ["bookings", "bookings.website", "bookings.embed"])
def test_released_booking_embed_restores_the_same_page_on_both_client_transports(native, key):
    space, client, objects = object_world(native)
    room, page = objects["room"], objects["room_page"]
    space.website_embed_origins = ["https://embed.example.test"]
    space.save(update_fields=["website_embed_origins"])
    response = client.patch(reverse("admin-bookable-space-detail", args=[room.pk]),
        {"name": "Retained public room 工房"}, format="json")
    assert response_pair(response) == (200, None), response.data
    page.released = True
    page.save(update_fields=["released"])
    BookingResourcePageSection.objects.create(page=page, kind="rules", slug="arrival",
        title="Arrival", body="Use the front desk.", visibility="published", position=0)
    url = reverse("website-embed", kwargs={"makerspace_slug": space.slug, "kind": "bookings", "public_token": room.public_token})
    response = client.get(url)
    assert response_pair(response) == (200, None)
    assert "Retained public room 工房" in response.content.decode()
    before = domain_rows()
    original = switch(space, key)
    with no_domain_writes():
        response = client.get(url)
    assert response_pair(response) == (404, "not_found"), getattr(response, "data", None)
    assert domain_rows() == before
    switch(space, key, original=original)
    assert domain_rows() == before
    response = client.get(url)
    assert response_pair(response) == (200, None)
    assert "Retained public room 工房" in response.content.decode()
    assert domain_rows() == before


@pytest.mark.parametrize("native", [False, True])
@pytest.mark.parametrize("key", ["bookings", "bookings.calendar_feed"])
def test_issued_calendar_token_and_booking_survive_refused_settings_and_feed_requests(native, key):
    from apps.accounts.models import User
    from apps.bookings.models import Booking
    space, client, objects = object_world(native)
    actor = User.objects.get(username="sx-real-object-manager")
    start = timezone.now() + timedelta(days=2)
    Booking.objects.create(space=objects["room"], member=actor, name="Retained calendar borrower", email="calendar@example.test",
        starts_at=start, ends_at=start + timedelta(hours=1))
    settings_url = reverse("member-booking-feed-settings", args=[space.slug])
    issued = client.post(settings_url, {}, format="json")
    assert response_pair(issued) == (200, None), issued.data
    feed_url = urlsplit(issued.data["feed_url"]).path
    assert response_pair(client.get(feed_url)) == (200, None)
    before = domain_rows()
    original = switch(space, key)
    for method, url in (("get", settings_url), ("post", settings_url), ("delete", settings_url), ("get", feed_url)):
        with no_domain_writes():
            response = getattr(client, method)(url, {}, format="json")
        assert response_pair(response) == (404, "module_disabled" if key == "bookings" else "feature_disabled"), response.data
        assert domain_rows() == before
    switch(space, key, original=original)
    assert domain_rows() == before
    response = client.get(feed_url)
    assert response_pair(response) == (200, None)
    assert "Retained room" in response.content.decode()
    assert domain_rows() == before

"""Public directory: `offers` and `next_event` on GET /api/public/makerspaces/."""

from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.bookings.models import BookableSpace
from apps.events.models import Event
from apps.makerspaces.models import Makerspace

pytestmark = pytest.mark.django_db
URL = "/api/public/makerspaces/"


def make_space(slug, modules=(), features=(), **values):
    space = Makerspace.objects.create(name=slug, slug=slug, **values)
    space.enabled_modules = list(modules)
    space.enabled_features = list(features)
    space.save(update_fields=["enabled_modules", "enabled_features"])
    return space


def make_event(space, title="Open night", days=2, **values):
    start = timezone.now() + timedelta(days=days)
    values.setdefault("is_public", True)
    return Event.objects.create(
        makerspace=space, title=title, status=Event.Status.PUBLISHED,
        starts_at=start, ends_at=start + timedelta(hours=2), **values,
    )


def row(slug):
    data = APIClient().get(URL).json()
    return next(item for item in data if item["slug"] == slug)


def test_events_offer_and_next_event_only_when_module_on_and_event_public():
    space = make_space("evt-on", modules=["events"])
    later = make_event(space, "Later", days=5)
    sooner = make_event(space, "Sooner", days=1)
    result = row("evt-on")
    assert "events" in result["offers"]
    assert result["next_event"]["title"] == "Sooner"
    assert result["next_event"]["public_url"] == f"/m/evt-on/events/{sooner.public_token}"
    assert later.public_token != sooner.public_token


def test_module_off_not_listed():
    space = make_space("evt-off", modules=[])
    make_event(space)
    result = row("evt-off")
    assert "events" not in result["offers"]
    assert result["next_event"] is None


def test_next_event_ignores_private_unlisted_past_and_offline():
    space = make_space("evt-hidden", modules=["events"])
    make_event(space, "Private", is_public=False)
    make_event(space, "Unlisted", listing=Event.Listing.UNLISTED)
    make_event(space, "Offline", page_state=Event.PageState.OFFLINE)
    make_event(space, "Past", days=-3)
    result = row("evt-hidden")
    assert result["next_event"] is None
    assert "events" not in result["offers"]


def test_bookings_listed_only_with_a_public_active_resource():
    space = make_space("book-hidden", modules=["bookings"])
    BookableSpace.objects.create(makerspace=space, name="Room", is_public=False)
    assert "bookings" not in row("book-hidden")["offers"]
    BookableSpace.objects.create(makerspace=space, name="Hall", is_public=True, is_active=True)
    assert "bookings" in row("book-hidden")["offers"]


def test_shop_and_inventory_follow_their_switches():
    space = make_space("shop-sp", modules=["shop", "public_inventory", "staff_admin"],  # loans.enabled is parented on staff_admin
                       features=["shop.online", "loans.enabled"])
    offers = row("shop-sp")["offers"]
    assert "shop" in offers and "inventory" in offers
    space.public_inventory_enabled = False
    space.save(update_fields=["public_inventory_enabled"])
    assert "inventory" not in row("shop-sp")["offers"]


def test_offers_are_ordered_and_contain_only_known_keys():
    make_space("ordered", modules=["events", "shop"], features=["shop.online"])
    make_event(Makerspace.objects.get(slug="ordered"))
    offers = row("ordered")["offers"]
    assert offers == [key for key in ("inventory", "machines", "events", "bookings", "shop", "memberships", "donations") if key in offers]


def test_directory_query_count_is_flat_across_spaces():
    first = make_space("flat-1", modules=["events", "bookings", "shop"], features=["shop.online"])
    make_event(first)  # same data shape per space, so only the number of spaces differs between the two requests
    BookableSpace.objects.create(makerspace=first, name="Room", is_public=True)
    with CaptureQueriesContext(connection) as one:
        APIClient().get(URL)
    for number in range(2, 6):
        space = make_space(f"flat-{number}", modules=["events", "bookings", "shop"], features=["shop.online"])
        make_event(space)
        BookableSpace.objects.create(makerspace=space, name="Room", is_public=True)
    with CaptureQueriesContext(connection) as five:
        APIClient().get(URL)
    # The first request also pays one-off cold-cache lookups, so five spaces may cost fewer queries than
    # one; an N+1 would make it cost MORE, which is the regression this guards.
    assert len(five) <= len(one)

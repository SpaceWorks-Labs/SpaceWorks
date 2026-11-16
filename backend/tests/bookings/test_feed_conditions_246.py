"""Decision 246: member booking feeds are per person and per space (isolation, token, refusal)."""
import pytest
from django.urls import reverse
from icalendar import Calendar
from rest_framework.test import APIClient

from tests.bookings.test_member_booking_api import book, setup

pytestmark = pytest.mark.django_db


def _feed_url(tenant, client):
    return client.post(reverse("member-booking-feed-settings", kwargs={"makerspace_slug": tenant.slug}),
                       {}, format="json").data["feed_url"]


def _uids(url):
    response = APIClient().get(url)
    assert response.status_code == 200
    return {str(event["UID"]) for event in Calendar.from_ical(response.content).walk("VEVENT")}


def test_one_spaces_feed_never_changes_when_another_space_books():
    mine, my_room, my_user, my_client = setup("fc246-a")
    theirs, their_room, their_user, _their_client = setup("fc246-b")
    book(my_room, my_user)
    url = _feed_url(mine, my_client)
    before = _uids(url)
    book(their_room, their_user)
    assert before and _uids(url) == before


def test_a_wrong_or_missing_token_is_not_a_feed_and_anonymous_cannot_create_one():
    tenant, _room, _user, client = setup("fc246-token")
    url = _feed_url(tenant, client)
    bad = url[: url.rfind("/") + 1] + "not-a-real-token" + (".ics" if url.endswith(".ics") else "")
    assert APIClient().get(bad).status_code in (403, 404)
    assert APIClient().post(reverse("member-booking-feed-settings", kwargs={"makerspace_slug": tenant.slug}),
                            {}, format="json").status_code in (401, 403)

"""L18 calendar sync: shift and combined bearer feeds, the public listed feed, and the feed switches."""

from datetime import timedelta
from urllib.parse import urlsplit

import pytest
from django.utils import timezone
from icalendar import Calendar
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.events.models import Event, PersonalCalendarFeed
from tests.l18_local.helpers import switch

pytestmark = pytest.mark.django_db


def _uids(response):
    assert response.status_code == 200, response.content
    return {str(item["UID"]) for item in Calendar.from_ical(response.content).walk("VEVENT")}


def _issue(client, space, kind):
    response = client.post(f"/api/v1/member/makerspaces/{space.pk}/calendar-feeds/{kind}/", {}, format="json")
    assert response.status_code == 200, response.content
    return urlsplit(response.json()["feed_url"]).path


def test_public_feed_lists_only_listed_published_live_events_and_is_off_by_default():
    from tests.events.checkin_helpers import make_event, make_space
    space = make_space("feed-public-l18")
    listed = make_event(space, "Open night", listing=Event.Listing.LISTED, page_state=Event.PageState.LIVE)
    make_event(space, "Private board meeting", is_public=False)
    make_event(space, "Secret jam", listing=Event.Listing.UNLISTED)
    make_event(space, "Taken offline", page_state=Event.PageState.OFFLINE)
    make_event(space, "Draft idea", status=Event.Status.DRAFT)
    url = f"/api/v1/public/{space.slug}/events-calendar.ics"
    assert APIClient().get(url).status_code == 404
    switch(space, "events.public_feed")
    response = APIClient().get(url)
    assert _uids(response) == {f"event-{listed.calendar_uid}@spaceworks"}
    for hidden in (b"Private board meeting", b"Secret jam", b"Taken offline", b"Draft idea"):
        assert hidden not in response.content


def test_shift_feed_has_only_my_approved_shifts_and_rotation_revocation_and_switch_kill_links(settings):
    from apps.events.contributions.models import EventShiftSignup
    from tests.events.programme.contributions.helpers import setup_shift
    from tests.l18_local.helpers import client
    space, event, _posting, shift, users, roles, _adapter = setup_shift(settings)
    mine = EventShiftSignup.objects.create(event=event, makerspace=space, shift=shift, assignment=roles[0],
                                           member=users[0], state="approved")
    EventShiftSignup.objects.create(event=event, makerspace=space, shift=shift, assignment=roles[1],
                                    member=users[1], state="approved")
    me = client(users[0])
    assert me.post(f"/api/v1/member/makerspaces/{space.pk}/calendar-feeds/shifts/", {}, format="json").status_code == 404
    switch(space, "events.shifts_feed")
    path = _issue(me, space, "shifts")
    feed = APIClient().get(path)
    assert _uids(feed) == {f"shift-{mine.pk}@spaceworks"}
    assert users[1].email.encode() not in feed.content and users[0].email.encode() not in feed.content
    row = PersonalCalendarFeed.objects.get(user=users[0], kind="shifts")
    assert len(bytes(row.token_digest)) == 32 and path.rsplit("/", 1)[1][:-4] not in bytes(row.token_digest).hex()
    rotated = _issue(me, space, "shifts")
    assert APIClient().get(path).status_code == 404 and APIClient().get(rotated).status_code == 200
    switch(space, "events.shifts_feed", on=False)
    assert APIClient().get(rotated).status_code == 404
    switch(space, "events.shifts_feed")
    assert me.delete(f"/api/v1/member/makerspaces/{space.pk}/calendar-feeds/shifts/").status_code == 204
    assert APIClient().get(rotated).status_code == 404
    assert set(AuditLog.objects.filter(action__startswith="calendar_feed.").values_list("action", flat=True)) == {
        "calendar_feed.created", "calendar_feed.rotated", "calendar_feed.revoked"}
    assert "token" not in str(list(AuditLog.objects.filter(action__startswith="calendar_feed.").values("meta")))


def test_combined_feed_has_only_the_persons_own_bookings_and_registrations():
    from apps.bookings.models import BookableSpace
    from tests.bookings.test_member_booking_api import book, member
    from tests.events.checkin_helpers import make_event, register
    from apps.makerspaces.models import Makerspace
    space = Makerspace.objects.create(name="combo", slug="combo-l18")
    room = BookableSpace.objects.create(makerspace=space, name="Room", approval_mode="instant")
    user, me = member(space, "combo-me")
    other, _ = member(space, "combo-other")
    mine = book(room, user)
    theirs = book(room, other, starts_at=mine.starts_at + timedelta(hours=3))
    event = make_event(space, "Members evening", starts_at=timezone.now() + timedelta(days=3))
    registration = register(event, user)
    register(make_event(space, "Someone else's class"), other)
    assert me.post(f"/api/v1/member/makerspaces/{space.pk}/calendar-feeds/combined/", {},
                   format="json").status_code == 404
    switch(space, "calendar.combined_feed")
    feed = APIClient().get(_issue(me, space, "combined"))
    uids = _uids(feed)
    assert f"booking-{mine.public_token}@spaceworks" in uids
    assert f"booking-{theirs.public_token}@spaceworks" not in uids
    assert any(uid.startswith(f"event-{event.calendar_uid}") for uid in uids)
    assert b"Someone else's class" not in feed.content and other.email.encode() not in feed.content
    assert registration.pk


def test_existing_feeds_answer_404_while_their_switch_is_off_and_keep_their_rows():
    from tests.bookings.test_member_booking_api import setup
    from tests.events.checkin_helpers import client_for, make_member, make_space
    space, room, user, client = setup("feed-switch-l18")
    issued = client.post(f"/api/v1/public/{space.slug}/my-bookings/calendar/", {}, format="json")
    assert issued.status_code == 200
    switch(space, "bookings.calendar_feed", on=False)
    assert APIClient().get(urlsplit(issued.json()["feed_url"]).path).status_code == 404
    assert client.get(f"/api/v1/public/{space.slug}/my-bookings/calendar/").status_code == 404
    events_space = make_space("feed-switch-events-l18")
    person = make_member(events_space, "feed-switch-member")
    events_client = client_for(person)
    url = f"/api/v1/member/makerspaces/{events_space.pk}/event-calendar-feed/"
    feed = events_client.post(url, {"confirm_bearer_risk": True}, format="json")
    assert feed.status_code == 200
    switch(events_space, "events.calendar_feed", on=False)
    assert APIClient().get(urlsplit(feed.json()["feed_url"]).path).status_code == 404
    assert events_client.get(url).status_code == 404
    switch(events_space, "events.calendar_feed")
    assert APIClient().get(urlsplit(feed.json()["feed_url"]).path).status_code == 200


def test_new_spaces_get_both_existing_feed_switches_on_by_default():
    from apps.makerspaces.models import Makerspace
    space = Makerspace.objects.create(name="defaults", slug="defaults-l18")
    assert {"bookings.calendar_feed", "events.calendar_feed"} <= set(space.enabled_features)
    assert not {"events.shifts_feed", "calendar.combined_feed", "events.public_feed", "finance.donations"} & set(
        space.enabled_features)

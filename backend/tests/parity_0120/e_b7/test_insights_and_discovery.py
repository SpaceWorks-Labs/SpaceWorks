"""E-B7 insights (k >= 10) and discovery filters (tag, organiser, public visibility)."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.events.models import Event, EventRegistration
from apps.events.organizer_models import EventOrganizer
from apps.events.programme.analytics_org import K, hosted_insights
from apps.events.website_discovery import organizer_name_matches, restrict_by_tag_and_organization
from apps.organizations.models import Organization
from tests.events.collab_helpers import make_event, make_member, make_space

pytestmark = pytest.mark.django_db


def past_event(space, title, days_ago=10):
    event = make_event(space, title=title)
    start = timezone.now() - timedelta(days=days_ago)
    Event.objects.filter(pk=event.pk).update(starts_at=start, ends_at=start + timedelta(hours=2))
    return Event.objects.get(pk=event.pk)


def attend(event, members):
    for member in members:
        EventRegistration.objects.create(event=event, member=member, status="attended")


def test_small_groups_are_suppressed():
    space = make_space("ins-small")
    attend(past_event(space, "Tiny"), [make_member(space, f"a{i}") for i in range(K - 1)])
    result = hosted_insights(Event.objects.filter(makerspace=space))
    assert result["top_events"] == []
    assert result["returning"] == {"suppressed": True, "attendees": None, "returning_percent": None}


def test_top_events_rank_by_attendance_and_returning_share():
    space = make_space("ins-big")
    members = [make_member(space, f"b{i}") for i in range(K + 2)]
    attend(past_event(space, "Big", 5), members)
    attend(past_event(space, "Medium", 20), members[:K])
    attend(past_event(space, "Ancient", 400), members)  # outside the 180-day window
    result = hosted_insights(Event.objects.filter(makerspace=space))
    assert [row["title"] for row in result["top_events"]] == ["Big", "Medium"]
    assert result["returning"]["attendees"] == K + 2
    assert result["returning"]["returning_percent"] == round(K * 100 / (K + 2), 1)


def test_tag_and_organiser_filters_need_the_switch_and_a_public_organiser():
    space = make_space("disc-a")
    event = make_event(space, is_public=True)
    Event.objects.filter(pk=event.pk).update(tags=["Robotics", "kids"])
    public_org = Organization.objects.create(name="Gear Club", slug="gear-club", public_profile_enabled=True)
    private_org = Organization.objects.create(name="Hidden Club", slug="hidden-club")
    EventOrganizer.objects.create(event=event, organization=public_org)
    other = make_event(space, is_public=True, title="Other")
    EventOrganizer.objects.create(event=other, organization=private_org)
    rows, spaces = Event.objects.filter(makerspace=space), [space]
    # Switch off: a tag or organiser filter returns nothing rather than being ignored.
    assert list(restrict_by_tag_and_organization(rows, spaces, "robotics", None)) == []
    space.enabled_features = ["events.discovery_filters"]
    space.save(update_fields=["enabled_features"])
    assert [e.pk for e in restrict_by_tag_and_organization(rows, spaces, "ROBOTICS", None)] == [event.pk]
    assert [e.pk for e in restrict_by_tag_and_organization(rows, spaces, None, "gear-club")] == [event.pk]
    assert list(restrict_by_tag_and_organization(rows, spaces, None, "hidden-club")) == []
    assert list(restrict_by_tag_and_organization(rows, spaces, "rob", None)) == []  # whole tags only
    assert set(rows.filter(pk__in=organizer_name_matches(spaces, "gear"))) == {event}
    assert list(rows.filter(pk__in=organizer_name_matches(spaces, "hidden"))) == []
    assert organizer_name_matches(spaces, "g") is None

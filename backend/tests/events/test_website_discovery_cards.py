from tests.events.website_helpers import make_page
"""Discovery cards preserve public policy without per-event detail queries."""

from dataclasses import asdict
from datetime import time

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.events.models import EventRegistration, EventSeries
from apps.events.models_website import EventPage
from apps.events.organizer_models import EventOrganizer
from apps.events.serializers_public import PublicEventSerializer
from apps.events.website_adapter import cards
from apps.events.website_visibility import discover_events
from apps.makerspaces.website_directory import directory_spaces, public_url
from apps.organizations.models import Organization, OrganizationMakerspace
from tests.events.ticketing_helpers import event_space, open_event
from tests.events.website_helpers import website_fixture

pytestmark = pytest.mark.django_db(transaction=True)


def organization_event(index):
    space = event_space(f"discovery-{index}")
    owner = Organization.objects.create(name=f"Owner {index}", slug=f"owner-{index}")
    organizer = Organization.objects.create(name=f"Organizer {index}", slug=f"organizer-{index}")
    inactive = Organization.objects.create(name="Inactive", slug=f"inactive-{index}", is_active=False)
    OrganizationMakerspace.objects.create(organization=owner, makerspace=space, relationship="owner")
    event = open_event(space, audience="participating_organizations", capacity=2)
    for organization in (owner, organizer, inactive):
        EventOrganizer.objects.create(event=event, organization=organization)
    EventRegistration.objects.create(event=event, name="Attendee", email=f"{index}@example.test", status="attended")
    return event


def test_discovery_query_count_is_bounded_for_a_full_multi_tenant_page(monkeypatch):
    event = organization_event(0)
    client = APIClient()
    route = "/api/v1/discover/events/"
    client.get(route)  # Resolve URL/serializer setup before measuring requests.

    def no_detail_serialization(*args, **kwargs):
        pytest.fail("Discovery must not run the full public detail serializer")

    monkeypatch.setattr(PublicEventSerializer, "to_representation", no_detail_serialization)
    with CaptureQueriesContext(connection) as single_queries:
        single = client.get(route)
    assert single.status_code == 200
    assert len(single.data["results"]) == 1
    for index in range(1, 24):
        organization_event(index)
    with CaptureQueriesContext(connection) as full_queries:
        full = client.get(route)
    assert full.status_code == 200
    assert full.data["count"] == len(full.data["results"]) == 24
    # Different hosts and organizations must still take one batch of reads.
    assert len(full_queries) <= len(single_queries) + 1
    assert len(full_queries) <= 15
    assert all(row["registration_count"] == 1 for row in full.data["results"])
    assert all(row["availability"] == "Limited" for row in full.data["results"])
    assert all("Inactive" not in row["audience_label"] for row in full.data["results"])
    row = next(row for row in full.data["results"] if row["url"] == public_url(event.makerspace, "events", event.public_token))
    assert row["audience_label"] == "Open to members of Organizer 0, Owner 0"
    assert not any("events_eventtickettype" in query["sql"].lower() for query in full_queries)


def test_card_fields_match_public_details_and_counts_remain_private_when_disabled():
    space, _, event, _, _ = website_fixture()
    event.capacity = 5
    event.description = "Description " * 50
    event.save(update_fields=["capacity", "description"])
    for index, status in enumerate(("registered", "attended", "waitlisted", "cancelled", "pending_approval")):
        EventRegistration.objects.create(event=event, name="Attendee", email=f"{index}@example.test", status=status)
    detail = PublicEventSerializer(event, context={"omit_website": True}).data
    projected = asdict(cards(list(discover_events(directory_spaces())))[0])
    for field in ("title", "location", "image_url", "availability", "registration_count"):
        assert projected[field] == detail[field]
    assert projected["date"] == detail["starts_at"]
    assert projected["description"] == detail["description"][:300]
    assert projected["registration_count"] == 2
    assert projected["audience_label"] == ""
    event.show_registration_count = False
    event.save(update_fields=["show_registration_count"])
    assert cards(list(discover_events(directory_spaces())))[0].registration_count is None


def test_discovery_batches_inherited_and_override_page_revisions_and_cover_images(monkeypatch):
    space = event_space("series-cards")
    event = open_event(space)
    series = EventSeries.objects.create(makerspace=space, title="Series", recurrence_timezone="UTC",
        dtstart_local_date=event.starts_at.date(), dtstart_local_time=time(0), duration_minutes=1440,
        recurrence_rule="FREQ=DAILY", image_key="series-cover")
    inherited_page = make_page(makerspace=space, series=series, revision=7, released=True)
    event.series = series
    event.series_occurrence_key = "inherited"
    event.series_revision = 1
    event.image_key = "ignored-cover"
    event.save(update_fields=["series", "series_occurrence_key", "series_revision", "image_key"])
    override = open_event(space, series=series, series_occurrence_key="override", series_revision=1,
                          image_key="own-cover", series_override_fields=["image_key"])
    own_page = make_page(makerspace=space, event=override, revision=3)
    core = open_event(space)
    monkeypatch.setattr("apps.inventory.public_image_storage.public_url", lambda key: f"https://images.test/{key}" if key else "")
    with CaptureQueriesContext(connection) as queries:
        result = cards(list(discover_events(directory_spaces())))
    by_url = {row.url: row for row in result}
    inherited = by_url[public_url(space, "events", event.public_token)]
    own = by_url[public_url(space, "events", override.public_token)]
    assert f":{inherited_page.pk}:7:True:" in inherited.revision
    assert f":{own_page.pk}:3:False:" in own.revision
    assert ":core:" in by_url[public_url(space, "events", core.public_token)].revision
    assert inherited.image_url == "https://images.test/series-cover"
    assert own.image_url == "https://images.test/own-cover"
    # One annotated event query and one organizer prefetch, even with missing pages.
    assert len(queries) == 2


def test_generated_destinations_share_the_canonical_short_event_route(settings):
    settings.PUBLIC_APP_BASE_URL = "https://frontend.example"
    space, _, event, _, _ = website_fixture()
    destination = f"https://frontend.example/e/{event.public_token}"
    client = APIClient()
    discovery = client.get("/api/v1/discover/events/")
    assert discovery.data["results"][0]["url"] == destination
    # The shared embed route no longer serves events (#143); L1's embed card has its own tests.
    assert client.get(f"/embed/{space.slug}/events/{event.public_token}/").status_code == 404
    assert f'content="{destination}"' in client.get(f"/share/events/{event.public_token}/").content.decode()
    space.frontend_domain = "custom.example"
    space.frontend_domain_status = "verified"
    space.save(update_fields=["frontend_domain", "frontend_domain_status"])
    assert public_url(space, "events", event.public_token) == f"https://custom.example/e/{event.public_token}"

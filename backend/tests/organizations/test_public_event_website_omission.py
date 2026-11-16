"""Organization cards must not expand released editorial content per event."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APIClient

from apps.events.models_website import (
    EventPage, EventPageSection, EventSession, EventSessionSpeaker,
)
from apps.events.organizer_models import EventOrganizer
from apps.organizations.models import Organization
from tests.events.ticketing_helpers import open_event
from tests.events.website_helpers import make_session, snapshot, website_fixture

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("event_count", [1, 24])
def test_organization_list_skips_all_website_queries_even_for_released_pages(event_count, settings):
    # Same trusted test host the events suite's autouse fixture provides for website routes.
    settings.INFRA_HOSTS = {*settings.INFRA_HOSTS, "testserver"}
    space, _, first, first_page, first_speaker = website_fixture()
    organization = Organization.objects.create(
        name="Public organizer", slug="public-organizer", public_profile_enabled=True,
    )
    for index in range(event_count):
        if index == 0:
            event, page, speaker = first, first_page, first_speaker
        else:
            event = open_event(space)
            page = EventPage.objects.create(makerspace=space, event=event, released=True)
            speaker = EventPageSection.objects.create(
                page=page, kind="speaker", slug="speaker", title="Speaker",
                body="Published biography", visibility="published",
            )
        session = make_session(
            page=page, slug="talk", title="Published talk", visibility="published",
            starts_at=event.starts_at, ends_at=event.ends_at,
        )
        EventSessionSpeaker.objects.create(session=session, speaker=speaker)
        # Publish again so the released revision includes the speaker link.
        snapshot(page)
        EventOrganizer.objects.create(event=event, organization=organization)

    client = APIClient()
    # Prove the fixture really has a released, publicly readable programme.
    detail = client.get(f"/api/v1/public/{space.slug}/events/{first.public_token}/")
    assert detail.status_code == 200
    assert detail.data["website"]["sessions"][0]["title"] == "Published talk"
    assert detail.data["website"]["sessions"][0]["speakers"] == [first_speaker.slug]

    url = reverse("public-organization-events", kwargs={"slug": organization.slug})
    with CaptureQueriesContext(connection) as queries:
        response = client.get(url)

    assert response.status_code == 200
    assert response.data["count"] == len(response.data["results"]) == event_count
    assert all(row["website"] is None for row in response.data["results"])
    assert all(row["host"]["slug"] == space.slug for row in response.data["results"])
    # Zero website reads at either page size, including sections and speaker links.
    assert not any(
        "events_eventpage" in query["sql"].lower()
        or "events_eventsession" in query["sql"].lower()
        for query in queries
    )

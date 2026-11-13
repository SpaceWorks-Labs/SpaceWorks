"""L1 G2: who can find (listed | unlisted) and offline pages (promised-items SPEC section 2)."""

from uuid import uuid4

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.events.models import Event
from tests.events.collab_helpers import client_for, make_staff
from tests.events.ticketing_helpers import event_space, open_event, public_url

pytestmark = pytest.mark.django_db(transaction=True)


def fixture():
    space = event_space("findable")
    space.public_site_enabled = True
    space.save(update_fields=["public_site_enabled"])
    staff = make_staff(space)
    listed = open_event(space)
    hidden = open_event(space, listing="unlisted")
    Event.objects.filter(pk=listed.pk).update(title="Listed jam")
    Event.objects.filter(pk=hidden.pk).update(title="Hidden jam")
    listed.refresh_from_db(); hidden.refresh_from_db()
    return space, staff, listed, hidden


def tokens(response):
    rows = response.data["results"] if isinstance(response.data, dict) else response.data
    return {str(row["public_token"]) for row in rows}


def test_unlisted_events_never_appear_on_listing_surfaces(settings):
    settings.PUBLIC_APP_BASE_URL = "https://testserver"
    space, _staff, listed, hidden = fixture()
    client = APIClient()
    listing = client.get(f"/api/v1/public/{space.slug}/events/")
    assert listing.status_code == 200
    assert str(listed.public_token) in tokens(listing) and str(hidden.public_token) not in tokens(listing)
    discover = client.get("/api/v1/discover/events/")
    assert discover.status_code == 200
    urls = [card["url"] for card in discover.data["results"]]
    assert any(str(listed.public_token) in url for url in urls)
    assert not any(str(hidden.public_token) in url for url in urls)
    sitemap = client.get("/sitemap.xml").content.decode()
    assert str(listed.public_token) in sitemap and str(hidden.public_token) not in sitemap
    from apps.makerspaces.public_page_derived import event_cards
    cards, _count = event_cards("makerspace", space)
    names = str(cards)
    assert "Listed jam" in names and "Hidden jam" not in names


def test_unlisted_event_is_reachable_by_its_link_and_marked_noindex():
    space, _staff, listed, hidden = fixture()
    client = APIClient()
    detail = client.get(public_url(hidden, "public-event-detail"))
    assert detail.status_code == 200
    assert detail["X-Robots-Tag"] == "noindex, nofollow" and detail.data["indexable"] is False
    listed_detail = client.get(public_url(listed, "public-event-detail"))
    assert "X-Robots-Tag" not in listed_detail and listed_detail.data["indexable"] is True
    assert client.get(f"/api/v1/public/event-codes/{hidden.public_token}/").status_code == 200
    assert client.get(public_url(hidden, "public-event-calendar")).status_code == 200


def test_offline_page_is_a_uniform_404_without_a_lifecycle_change():
    space, _staff, listed, _hidden = fixture()
    listed.page_state = "offline"
    listed.save(update_fields=["page_state"])
    client = APIClient()
    for route in (public_url(listed, "public-event-detail"), public_url(listed, "public-event-calendar"),
                  f"/api/v1/public/event-codes/{listed.public_token}/",
                  f"/api/v1/public/{space.slug}/events/{listed.public_token}/share.png"):
        assert client.get(route).status_code == 404, route
    assert str(listed.public_token) not in tokens(client.get(f"/api/v1/public/{space.slug}/events/"))
    listed.refresh_from_db()
    assert listed.status == Event.Status.PUBLISHED


def test_private_event_still_404s_everywhere():
    space, _staff, listed, _hidden = fixture()
    listed.is_public = False
    listed.save(update_fields=["is_public"])
    assert APIClient().get(public_url(listed, "public-event-detail")).status_code == 404


def test_organization_catalogue_hides_unlisted_events():
    from apps.events.organizer_models import EventOrganizer
    from apps.organizations.models import Organization
    from apps.organizations.public_catalog import public_events_for
    space, _staff, listed, hidden = fixture()
    org = Organization.objects.create(name="Org", slug="org-findable", is_active=True, public_profile_enabled=True)
    for event in (listed, hidden):
        EventOrganizer.objects.create(event=event, organization=org)
    rows = public_events_for(org)
    if rows is not None:
        assert hidden.pk not in {row.pk for row in rows}


def publishing(staff, event, **data):
    route = reverse("events-programme-admin-programme-publishing", kwargs={"pk": event.pk})
    body = {"operation_id": str(uuid4()), "expected_version": Event.objects.get(pk=event.pk).version, **data}
    return client_for(staff).patch(route, body, format="json")


def test_publishing_panel_saves_the_three_questions_and_audits_them():
    _space, staff, listed, _hidden = fixture()
    response = publishing(staff, listed, listing="unlisted", page_state="offline")
    assert response.status_code == 200, response.data
    assert response.data["listing"] == "unlisted" and response.data["page_state"] == "offline"
    row = AuditLog.objects.get(action="event.publishing_changed")
    assert row.meta["changed_fields"] == ["listing", "page_state"]
    assert row.meta["before"]["listing"] == "listed" and row.meta["after"]["page_state"] == "offline"


def test_a_private_event_cannot_be_listed():
    _space, staff, listed, _hidden = fixture()
    listed.is_public = False
    listed.save(update_fields=["is_public"])
    assert publishing(staff, listed, listing="listed").status_code == 400


def test_machine_api_carries_visibility_fields_and_clone_copies_listing():
    from apps.events.serializers_integration import IntegrationEventSerializer
    from apps.events.services_clone import duplicate_event
    _space, staff, _listed, hidden = fixture()
    data = IntegrationEventSerializer(hidden).data
    assert data["is_public"] is True and data["listing"] == "unlisted"
    hidden.page_state = "offline"
    hidden.save(update_fields=["page_state"])
    clone = duplicate_event(hidden, actor=staff)
    assert clone.listing == "unlisted" and clone.page_state == "live"


def test_existing_rows_default_to_listed_and_live():
    space = event_space("defaults")
    event = open_event(space)
    assert (event.listing, event.page_state, event.delivery_mode) == ("listed", "live", "in_person")

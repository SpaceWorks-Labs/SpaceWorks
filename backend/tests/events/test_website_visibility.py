from tests.events.website_helpers import make_session
from datetime import timedelta, datetime, timezone as dt_timezone

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.events.models import Event
from apps.events.models_website import EventPageAsset, EventPageSection, EventSession
from apps.events.serializers_public import PublicEventSerializer
from apps.makerspaces.website_directory import public_url
from tests.events.website_helpers import website_fixture, url
from tests.events.website_helpers import snapshot

pytestmark = pytest.mark.django_db(transaction=True)


def test_public_event_list_skips_website_queries_but_detail_keeps_released_content():
    space, _, event, page, _ = website_fixture()
    EventPageSection.objects.create(page=page, kind="faq", slug="faq", title="Released FAQ", visibility="published")
    make_session(page=page, slug="talk", title="Talk", starts_at=event.starts_at,
                                ends_at=event.ends_at, visibility="published")
    EventPageAsset.objects.create(page=page, object_key="private-list-image", size_bytes=4, alt_text="Photo")
    base = f"/api/v1/public/{space.slug}/events/"
    with CaptureQueriesContext(connection) as queries:
        response = APIClient().get(base)
    assert response.status_code == 200
    assert response.data and all(row["website"] is None for row in response.data)
    website_tables = ("events_eventpage", "events_eventsession")
    assert not any(table in query["sql"].lower() for query in queries for table in website_tables)
    detail = APIClient().get(f"{base}{event.public_token}/")
    assert detail.status_code == 200
    assert {row["slug"] for row in detail.data["website"]["sections"]} == {"ada", "faq"}
    assert detail.data["website"]["sessions"][0]["slug"] == "talk"


@pytest.mark.parametrize("status", ["published", "draft", "cancelled", "completed"])
@pytest.mark.parametrize("released", [True, False])
@pytest.mark.parametrize("enabled", [True, False])
def test_release_matrix_covers_all_enhanced_projections(status, released, enabled, monkeypatch):
    space, _, event, page, speaker = website_fixture(released=released)
    event.status = status
    event.save(update_fields=["status"])
    if not enabled:
        space.enabled_features.remove("events.website")
        space.save(update_fields=["enabled_features"])
        event.makerspace = space
    asset = EventPageAsset.objects.create(page=page,
        object_key=f"events/website/{space.pk}/{page.pk}/photo.webp", size_bytes=100, alt_text="Portrait of Ada")
    speaker.asset = asset
    speaker.save(update_fields=["asset"])
    make_session(page=page, slug="talk", title="Talk", starts_at=event.starts_at, ends_at=event.ends_at, visibility="published")
    monkeypatch.setattr("apps.events.views_website_admin.image_response", lambda a: __import__("django.http", fromlist=["HttpResponse"]).HttpResponse(b"image", content_type="image/webp"))
    monkeypatch.setattr("apps.events.views_website_public.image_response", lambda a: __import__("django.http", fromlist=["HttpResponse"]).HttpResponse(b"image", content_type="image/webp"))
    client = APIClient()
    suffixes = ["", "schedule/", "speakers/ada/", "sections/ada/", "sessions/talk/", f"assets/{asset.pk}/"]
    routes = [url(event, suffix) for suffix in suffixes]
    # The shared embed route no longer serves events (#143); L1's embed card is tested separately.
    routes += [f"/share/events/{event.public_token}/"]
    expected = status == "published" and released and enabled
    for route in routes:
        response = client.get(route)
        assert response.status_code == (200 if expected else 404), (route, response.status_code)
    assert (PublicEventSerializer(event).data["website"] is not None) is expected


@pytest.mark.parametrize("condition", ["private", "expired", "module_off", "archived", "inactive", "unreleased", "draft_section"])
def test_images_and_items_never_bypass_public_gate(condition, monkeypatch):
    space, _, event, page, speaker = website_fixture()
    asset = EventPageAsset.objects.create(page=page,
        object_key=f"events/website/{space.pk}/{page.pk}/photo.webp", size_bytes=100, alt_text="Ada")
    speaker.asset = asset
    if condition == "draft_section": speaker.visibility = "draft"
    speaker.save(update_fields=["asset", "visibility"])
    snapshot(page)
    if condition == "private": event.is_public = False
    if condition == "expired": event.ends_at = timezone.now() - timedelta(seconds=1); event.starts_at = event.ends_at - timedelta(hours=1)
    event.save(update_fields=["is_public", "starts_at", "ends_at"])
    if condition == "module_off": space.enabled_modules.remove("events")
    if condition == "archived": space.archived_at = timezone.now()
    if condition == "inactive": space.lifecycle_state = "importing"
    space.save(update_fields=["enabled_modules", "archived_at", "lifecycle_state"])
    if condition == "unreleased": page.released = False; page.save(update_fields=["released"])
    called = []
    monkeypatch.setattr("apps.events.views_website_public.image_response", lambda a: called.append(a))
    assert APIClient().get(url(event, f"assets/{asset.pk}/")).status_code == 404
    assert not called


def test_draft_rows_are_absent_and_private_asset_cannot_be_guessed():
    space, _, event, page, _ = website_fixture()
    asset = EventPageAsset.objects.create(page=page, object_key="private-unused", size_bytes=2, alt_text="Secret")
    EventPageSection.objects.create(page=page, kind="faq", slug="secret", title="Private FAQ", visibility="draft", asset=asset)
    response = APIClient().get(url(event))
    assert response.status_code == 200
    assert "Private FAQ" not in str(response.data)
    assert "object_key" not in str(response.data)
    assert APIClient().get(url(event, "sections/secret/")).status_code == 404
    assert APIClient().get(url(event, f"assets/{asset.pk}/")).status_code == 404


def test_discover_pagination_filters_and_directory_consent(settings):
    settings.PUBLIC_APP_BASE_URL = "https://testserver"
    settings.ALLOWED_HOSTS = [*settings.ALLOWED_HOSTS, "custom.example"]
    space, _, event, _, _ = website_fixture()
    for n in range(25):
        Event.objects.create(makerspace=space, title=f"Workshop {n}", starts_at=event.starts_at,
            ends_at=event.ends_at, status="published", is_public=True, show_registration_count=False)
    response = APIClient().get("/api/v1/discover/events/")
    assert response.status_code == 200
    assert response.data["count"] == 26
    assert len(response.data["results"]) == 24
    assert response.data["next"]
    assert all(row["registration_count"] is None for row in response.data["results"] if row["title"].startswith("Workshop "))
    space.frontend_domain = "custom.example"
    space.frontend_domain_status = "verified"
    space.hidden_from_central_directory = True
    space.save(update_fields=["frontend_domain", "frontend_domain_status", "hidden_from_central_directory"])
    assert APIClient().get("/api/v1/discover/events/").data["count"] == 0
    assert APIClient().get(url(event)).status_code == 200  # Directory consent does not change direct access.


def test_local_date_filter_uses_each_tenants_day():
    space, _, event, _, _ = website_fixture()
    space.timezone = "Pacific/Kiritimati"
    space.save(update_fields=["timezone"])
    start = timezone.now() + timedelta(days=3)
    start = start.replace(hour=16, minute=0, second=0, microsecond=0)
    event.starts_at = start; event.ends_at = start + timedelta(hours=1)
    event.save(update_fields=["starts_at", "ends_at"])
    from apps.makerspaces.local_time import to_local
    local_day = to_local(space, start).date().isoformat()
    result = APIClient().get("/api/v1/discover/events/", {"date_from": local_day, "date_to": local_day})
    assert result.data["count"] == 1


def test_share_cache_rechecks_visibility_and_uses_only_cover(settings):
    space, _, event, page, _ = website_fixture()
    route = f"/share/events/{event.public_token}/"
    event.title = '<script>alert("title")</script>'
    event.save(update_fields=["title"])
    response = APIClient().get(route)
    assert response.status_code == 200
    html = response.content.decode()
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert response["X-Robots-Tag"] == "noindex"
    page.released = False; page.save(update_fields=["released"])
    assert APIClient().get(route).status_code == 404


def test_sitemap_custom_origin_and_unknown_host(settings):
    settings.PUBLIC_APP_BASE_URL = "https://testserver"
    settings.ALLOWED_HOSTS = [*settings.ALLOWED_HOSTS, "custom.example"]
    space, _, event, _, _ = website_fixture()
    assert str(event.public_token) in APIClient().get("/sitemap.xml").content.decode()
    space.frontend_domain = "custom.example"; space.frontend_domain_status = "verified"
    space.hidden_from_central_directory = True
    space.save(update_fields=["frontend_domain", "frontend_domain_status", "hidden_from_central_directory"])
    response = APIClient().get("/sitemap.xml", HTTP_HOST="custom.example")
    assert response.status_code == 200
    assert f"https://custom.example/e/{event.public_token}" in response.content.decode()
    assert str(event.public_token) not in APIClient().get("/sitemap.xml").content.decode()

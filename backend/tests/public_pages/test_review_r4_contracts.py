"""Round 4 covers real HTTP client gates, malformed writes and rendered contracts."""

from datetime import timedelta
from io import BytesIO
import json
from pathlib import Path
import re
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import UUID

import pytest
from rest_framework.renderers import JSONRenderer
from rest_framework.test import APIClient

from apps.events.models_website import EventPage, EventPageAsset
from apps.events.services_website import save_content, set_release
from apps.events.website_adapter import card
from apps.makerspaces.public_page_contract import empty_document
from apps.makerspaces.public_page_projection import presentation
from apps.makerspaces.public_page_serializers import PublicPageProjection
from apps.makerspaces.website_views import DiscoverySerializer
from tests.events.collab_helpers import client_for
from tests.events.website_helpers import staff_url

pytestmark = pytest.mark.django_db(transaction=True)


def released_cover(event_owner):
    space, actor, event = event_owner
    save_content(event, actor=actor, data={"revision": 0, "sections": [], "sessions": []})
    page = EventPage.objects.get(event=event)
    asset = EventPageAsset.objects.create(page=page, size_bytes=4, alt_text="Workshop cover",
        object_key=f"events/website/{space.pk}/{page.pk}/cover.webp")
    document = empty_document("event")
    document.update(cover_mode="asset", cover_asset_id=asset.pk)
    save_content(event, actor=actor, data={"revision": page.revision, "sections": [],
        "sessions": [], "editorial_document": document})
    page.refresh_from_db()
    set_release(event, actor=actor, released=True, revision=page.revision)
    return space, actor, event, page, asset


@pytest.mark.parametrize("withdrawal", ["unrelease", "module", "site", "private", "expired", "cover_removed", "hero_hidden"])
def test_cover_browser_and_crawler_paths_repeat_live_gates(event_owner, settings, monkeypatch, withdrawal):
    space, actor, event, page, asset = released_cover(event_owner)
    settings.API_CLIENT_AUTH_REQUIRED = True
    settings.PLATFORM_STAFF_ORIGINS = ["http://testserver"]
    from apps.evidence import storage
    monkeypatch.setattr(storage, "object_size", lambda key: 4)
    monkeypatch.setattr(storage, "_client", lambda: SimpleNamespace(get_object=lambda **kw: {"Body": BytesIO(b"webp")}))
    client = APIClient()
    browser_url = urlsplit(card(event).image_url).path
    headers = {"HTTP_X_PUBLISHABLE_KEY": space.public_api_key, "HTTP_ORIGIN": "http://testserver"}
    assert client.get(browser_url).status_code == 401
    browser = client.get(browser_url, **headers)
    assert browser.status_code == 200 and browser.content == b"webp"
    assert "no-store" in browser["Cache-Control"]
    for route in (f"/share/e/{event.public_token}/", f"/share/events/{event.public_token}/"):
        response = client.get(route)
        assert response.status_code == 200
        image = re.search(r'property="og:image" content="([^"]+)"', response.content.decode()).group(1)
        share_url = urlsplit(image).path
        assert share_url == f"/share/e/{event.public_token}/cover/"
        crawler = client.get(share_url)  # No Origin, key or staff/member credentials.
        assert crawler.status_code == 200 and crawler.content == b"webp"
        assert crawler["Content-Type"] == "image/webp"
        assert "no-store" in crawler["Cache-Control"]
        assert crawler["X-Content-Type-Options"] == "nosniff"
    if withdrawal == "unrelease":
        page.refresh_from_db()
        set_release(event, actor=actor, released=False, revision=page.revision)
    elif withdrawal in {"cover_removed", "hero_hidden"}:
        from apps.events.website_projection import project
        data = project(event)
        if withdrawal == "cover_removed":
            data["editorial_document"].update(cover_mode="none", cover_asset_id=None)
        else:
            data["section_enabled"]["HERO"] = False
        save_content(event, actor=actor, data=data)
        page.refresh_from_db()
        set_release(event, actor=actor, released=True, revision=page.revision)
    elif withdrawal == "module":
        space.enabled_modules.remove("events")
        space.save(update_fields=["enabled_modules"])
    elif withdrawal == "site":
        space.public_site_enabled = False
        space.save(update_fields=["public_site_enabled"])
    elif withdrawal == "private":
        event.is_public = False
        event.save(update_fields=["is_public"])
    else:
        from django.utils import timezone
        event.starts_at = timezone.now() - timedelta(hours=2)
        event.ends_at = timezone.now() - timedelta(hours=1)
        event.save(update_fields=["starts_at", "ends_at"])
    assert client.get(browser_url, **headers).status_code in {401, 404}
    assert client.get(share_url).status_code == 404


def test_share_cover_rejects_foreign_and_unknown_browser_origins(event_owner, settings, monkeypatch):
    from apps.makerspaces.models import Makerspace
    _, _, event, _, _ = released_cover(event_owner)
    settings.API_CLIENT_AUTH_REQUIRED = True
    settings.ALLOWED_HOSTS = ["testserver", "foreign.example.test"]
    Makerspace.objects.create(name="Other", slug="other-cover", frontend_domain="foreign.example.test",
                              frontend_domain_status="verified")
    def no_storage(*args, **kwargs):
        pytest.fail("Scope refusals must precede private storage access")
    monkeypatch.setattr("apps.evidence.storage.object_size", no_storage)
    route = f"/share/e/{event.public_token}/cover/"
    for headers in ({"HTTP_ORIGIN": "https://foreign.example.test"},
                    {"HTTP_REFERER": "https://foreign.example.test/page"},
                    {"HTTP_HOST": "foreign.example.test"},
                    {"HTTP_ORIGIN": "https://unknown.example.test"}):
        assert APIClient().get(route, **headers).status_code == 404


@pytest.mark.parametrize("field", ["section_order", "section_enabled"])
@pytest.mark.parametrize("value", [None, 1, "invalid", [], {"invalid": True}])
def test_malformed_group_fields_return_http_400_without_creating_page(event_owner, field, value):
    _, actor, event = event_owner
    response = client_for(actor).put(staff_url(event), {
        "revision": 0, "sections": [], "sessions": [], field: value}, format="json")
    assert response.status_code == 400
    assert not EventPage.objects.filter(event=event).exists()


def test_round_four_render_payloads_are_exact_serializer_output(event_owner, settings):
    fixtures = json.loads((Path(__file__).parent / "fixtures/review-r4.json").read_text())
    assert DiscoverySerializer(fixtures["discovery"]).data == fixtures["discovery"]
    assert PublicPageProjection(fixtures["palette_page"]).data == fixtures["palette_page"]
    space, actor, event, _, _ = released_cover(event_owner)
    settings.PUBLIC_APP_BASE_URL = "https://tenant.example.test"
    # Stable fixture IDs/dates stand in for generated identities; all fields come from the live card.
    event.public_token = UUID("10000000-0000-4000-8000-000000000004")
    from dataclasses import asdict
    serialized = asdict(card(event))
    serialized.update(revision="fixture-revision", date="2099-10-17T04:30:00Z")
    serialized["image_url"] = re.sub(r"/assets/\d+/", "/assets/12/", serialized["image_url"])
    assert serialized == fixtures["discovery"]["results"][0]
    resolved = presentation("makerspace", SimpleNamespace(theme_config={}), {"accent_choice": "workshop_orange"})
    assert json.loads(JSONRenderer().render(resolved)) == fixtures["palette_page"]["presentation"]

"""Crawler, framing and directory paths share the core public-event predicate."""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from tests.events.website_helpers import url, website_fixture

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("condition", ["private", "draft", "cancelled", "expired", "module_off", "archived", "inactive"])
def test_crawlers_embeds_sitemap_and_discover_cannot_bypass_public_predicate(condition, settings):
    settings.PUBLIC_APP_BASE_URL = "https://testserver"
    space, _, event, _, _ = website_fixture()
    if condition == "private":
        event.is_public = False
    if condition in {"draft", "cancelled"}:
        event.status = condition
    if condition == "expired":
        event.ends_at = timezone.now() - timedelta(seconds=1)
        event.starts_at = event.ends_at - timedelta(hours=1)
    event.save(update_fields=["is_public", "status", "starts_at", "ends_at"])
    if condition == "module_off":
        space.enabled_modules.remove("events")
    if condition == "archived":
        space.archived_at = timezone.now()
    if condition == "inactive":
        space.lifecycle_state = "importing"
    space.save(update_fields=["enabled_modules", "archived_at", "lifecycle_state"])
    client = APIClient()
    for route in (url(event), f"/embed/{space.slug}/events/{event.public_token}/", f"/share/events/{event.public_token}/"):
        assert client.get(route).status_code == 404, route
    discover = client.get("/api/v1/discover/events/")
    assert discover.status_code == 200 and discover.data["count"] == 0
    sitemap = client.get("/sitemap.xml")
    assert sitemap.status_code == 200
    assert str(event.public_token) not in sitemap.content.decode()


def test_embed_feature_is_rechecked_without_hiding_other_public_surfaces(settings):
    settings.PUBLIC_APP_BASE_URL = "https://testserver"
    space, _, event, _, _ = website_fixture()
    route = f"/embed/{space.slug}/events/{event.public_token}/"
    client = APIClient()
    # Owner decision #143: the shared embed route never serves events, embed switch on or off.
    assert client.get(route).status_code == 404
    space.enabled_features.remove("events.embed")
    space.save(update_fields=["enabled_features"])
    assert client.get(route).status_code == 404
    assert client.get(url(event)).status_code == 200
    assert client.get(f"/share/events/{event.public_token}/").status_code == 200
    assert client.get("/api/v1/discover/events/").data["count"] == 1
    assert str(event.public_token) in client.get("/sitemap.xml").content.decode()

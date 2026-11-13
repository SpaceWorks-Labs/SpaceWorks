"""Round 5 frontend review: tenant-domain canonical links, empty derived sections, event fixture shape."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.utils import timezone
from rest_framework.renderers import JSONRenderer

from apps.makerspaces.models import Makerspace
from apps.makerspaces.public_page_access import canonical_url
from apps.makerspaces.public_page_derived import derived_payload
from apps.makerspaces.public_page_projection import project_sections

pytestmark = pytest.mark.django_db(transaction=True)
FRONTEND_FIXTURES = Path(__file__).resolve().parents[3] / "frontend" / "src" / "features" / "publicPages" / "fixtures"


def verified(space):
    space.frontend_domain, space.frontend_domain_status = "tenant.example.test", Makerspace.DomainStatus.VERIFIED
    space.save(update_fields=["frontend_domain", "frontend_domain_status"])
    return space


def test_verified_domain_makerspace_without_handle_links_to_its_origin_root(page_owner, settings):
    from apps.organizations.public_catalog import archive_card, space_card
    settings.PUBLIC_APP_BASE_URL = "https://platform.example.test"
    space, _ = page_owner
    assert canonical_url("makerspace", space) == "https://platform.example.test/m/page-lab"
    verified(space)
    # A verified domain boots the single-space SPA, which has no /m/<slug> route.
    assert canonical_url("makerspace", space) == "https://tenant.example.test/"
    assert canonical_url("makerspace", space, "forge") == "https://tenant.example.test/forge"
    assert space_card(space)["canonical_url"] == "https://tenant.example.test/"
    now = timezone.now()
    event = SimpleNamespace(title="Past jam", description="Done", starts_at=now, ends_at=now, makerspace=space)
    assert archive_card(event)["host"]["canonical_url"] == "https://tenant.example.test/"


def test_pending_or_unverified_domain_keeps_the_platform_slug_route(page_owner, settings):
    settings.PUBLIC_APP_BASE_URL = "https://platform.example.test"
    space, _ = page_owner
    space.frontend_domain, space.frontend_domain_status = "tenant.example.test", Makerspace.DomainStatus.PENDING
    space.save(update_fields=["frontend_domain", "frontend_domain_status"])
    assert canonical_url("makerspace", space) == "https://platform.example.test/m/page-lab"


def test_organization_canonical_url_is_unchanged(settings):
    settings.PUBLIC_APP_BASE_URL = "https://platform.example.test"
    org = SimpleNamespace(slug="builders")
    assert canonical_url("organization", org) == "https://platform.example.test/o/builders"


STATS = {"title": "Numbers", "show_public_inventory_units": False, "show_published_event_count": False,
         "publish_public_member_count": False}


def test_empty_stats_and_private_location_are_omitted(page_owner):
    space, _ = page_owner
    assert derived_payload("makerspace", space, "stats", dict(STATS)) is None
    assert derived_payload("makerspace", space, "location", {"title": "Find us", "enabled_publicly": False,
                                                             "source": "entered", "address": "Secret"}) is None
    shown = derived_payload("makerspace", space, "location", {"title": "Visit", "enabled_publicly": True, "source": "makerspace_public"})
    assert shown["enabled_publicly"] is True and shown["title"] == "Visit"


def test_projection_drops_empty_derived_sections_but_keeps_the_rest(page_owner):
    space, _ = page_owner
    document = {"sections": [
        {"id": "30000000-0000-4000-8000-000000000001", "type": "stats", "enabled": True, "payload": dict(STATS)},
        {"id": "30000000-0000-4000-8000-000000000002", "type": "location", "enabled": True,
         "payload": {"title": "Find us", "enabled_publicly": False, "source": "entered"}},
        {"id": "30000000-0000-4000-8000-000000000003", "type": "about", "enabled": True,
         "payload": {"title": "Story", "markdown": "Hello"}},
    ]}
    assert [row["type"] for row in project_sections("makerspace", space, None, document=document)] == ["about"]


def test_frontend_event_fixture_matches_the_public_website_serializer(event_owner):
    from apps.events.serializers_website import PublicWebsiteSerializer
    from apps.events.website_projection import project
    from tests.public_pages.test_l1_event_revisions import released
    space, _, event = event_owner
    space.theme_config, space.cover_image_key, space.logo_key = {}, "", ""
    space.save(update_fields=["theme_config", "cover_image_key", "logo_key"])
    event.image_key = ""
    event.save(update_fields=["image_key"])
    released(event_owner)
    live = json.loads(JSONRenderer().render(PublicWebsiteSerializer(project(event, public=True)).data))
    fixture = json.loads((FRONTEND_FIXTURES / "event_released_public.json").read_text(encoding="utf-8"))
    assert set(fixture) == set(live)
    assert fixture["cover"] is None and live["cover"] is None
    assert fixture["presentation"] == live["presentation"]
    assert set(fixture["editorial_document"]) == set(live["editorial_document"])
    assert set(fixture["sessions"][0]) == set(live["sessions"][0])
    assert PublicWebsiteSerializer(fixture).data == fixture

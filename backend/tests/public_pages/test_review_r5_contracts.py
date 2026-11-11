"""Round 5: crawler-readable page cover route and lock-free editor image streaming."""

from datetime import timedelta
from io import BytesIO
import re
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest
from django.db import connection
from django.urls import resolve, reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.makerspaces import public_page_services as pages
from apps.makerspaces.models_profiles import PublicHandleRedirect
from tests.events.collab_helpers import client_for
from tests.public_pages.test_l1_assets import picture, private_store  # noqa: F401  (fixture)

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def stored_bytes(monkeypatch):
    from apps.evidence import storage
    monkeypatch.setattr(storage, "object_size", lambda key: 4)
    monkeypatch.setattr(storage, "_client", lambda: SimpleNamespace(get_object=lambda **kw: {"Body": BytesIO(b"webp")}))


def published_cover(kind, owner, actor, handle, *, cover_mode="asset"):
    from apps.makerspaces import public_page_assets as assets
    state = pages.change_handle(kind, owner.pk, actor=actor, version=0, handle=handle)
    result = assets.upload(kind, owner.pk, actor=actor, version=state["version"], file=picture(), alt_text="Workbench")
    document = result["state"]["document"]
    if cover_mode == "asset":
        document.update(cover_mode="asset", cover_asset_id=result["asset"]["id"])
    else:
        document.update(cover_mode=cover_mode, cover_asset_id=None)
    state = pages.save(kind, owner.pk, actor=actor, version=result["state"]["version"], document=document)
    state = pages.publish(kind, owner.pk, actor=actor, version=state["version"], draft_revision_id=state["draft_revision_id"])
    return state, result["asset"]["id"]


def og_image(client, handle):
    response = client.get(f"/share/pages/{handle}/")
    assert response.status_code == 200
    match = re.search(r'property="og:image" content="([^"]+)"', response.content.decode())
    return match.group(1) if match else None


def assert_crawler_image(client, route):
    crawler = client.get(route)  # No Origin, publishable key or credentials.
    assert crawler.status_code == 200 and crawler.content == b"webp"
    assert crawler["Content-Type"] == "image/webp"
    assert "no-store" in crawler["Cache-Control"]
    assert crawler["X-Content-Type-Options"] == "nosniff"


def test_cover_route_is_named_and_scoped_as_a_handle_route():
    from apps.makerspaces.origin_scope_routes_public_pages import HANDLE_ROUTES
    assert reverse("public-page-cover-share", kwargs={"handle": "our.lab"}) == "/share/pages/our.lab/cover/"
    assert resolve("/share/pages/our.lab/cover/").url_name == "public-page-cover-share"
    assert "public-page-cover-share" in HANDLE_ROUTES


def test_makerspace_share_card_points_crawlers_at_unprotected_cover(page_owner, private_store, stored_bytes, settings):
    space, actor = page_owner
    _, asset_id = published_cover("makerspace", space, actor, "cover.lab")
    settings.API_CLIENT_AUTH_REQUIRED = True
    client = APIClient()
    assert client.get(f"/api/v1/public/{space.slug}/page/assets/{asset_id}/").status_code == 401
    image = og_image(client, "cover.lab")
    assert image == "http://testserver/share/pages/cover.lab/cover/"
    assert_crawler_image(client, urlsplit(image).path)


def test_organization_share_card_points_crawlers_at_unprotected_cover(settings, private_store, stored_bytes):
    from apps.accounts.models import User
    from apps.organizations.models import Organization, OrganizationMembership
    settings.INFRA_HOSTS = ["testserver", "localhost"]
    settings.PUBLIC_APP_BASE_URL = "http://testserver"
    org = Organization.objects.create(name="Cover builders", slug="cover-builders", public_profile_enabled=True)
    governor = User.objects.create_user(username="cover-governor", account_kind="member")
    OrganizationMembership.objects.create(organization=org, user=governor, governance_actions=["manage_organization_profile"])
    _, asset_id = published_cover("organization", org, governor, "cover.org")
    settings.API_CLIENT_AUTH_REQUIRED = True
    client = APIClient()
    assert client.get(f"/api/v1/public/organizations/{org.slug}/page/assets/{asset_id}/").status_code == 401
    image = og_image(client, "cover.org")
    assert image == "http://testserver/share/pages/cover.org/cover/"
    assert_crawler_image(client, urlsplit(image).path)


def test_cover_route_404s_for_redirected_handle(page_owner, private_store, stored_bytes, settings):
    space, actor = page_owner
    published_cover("makerspace", space, actor, "cover.lab")
    now = timezone.now()
    PublicHandleRedirect.objects.create(makerspace=space, handle="old.lab", released_at=now,
                                        expires_at=now + timedelta(days=1))
    settings.API_CLIENT_AUTH_REQUIRED = True
    client = APIClient()
    assert client.get("/share/pages/old.lab/").status_code == 302
    assert client.get("/share/pages/old.lab/cover/").status_code == 404
    assert client.get("/share/pages/cover.lab/cover/").status_code == 200


def test_cover_route_404s_for_member_handle(settings, stored_bytes):
    from apps.accounts.models import User
    from apps.makerspaces.models import Makerspace, MakerspaceMembership
    from apps.makerspaces.models_profiles import MemberProfile, PublicHandle
    settings.INFRA_HOSTS = ["testserver", "localhost"]
    space = Makerspace.objects.create(name="Profile lab", slug="profile-lab", public_site_enabled=True)
    user = User.objects.create_user(username="cover-maker", email="cover-maker@example.test")
    membership = MakerspaceMembership.objects.create(makerspace=space, user=user, role="custom",
                                                     assigned_role=space.roles.get(slug="member"))
    profile = MemberProfile.objects.create(membership=membership, public_visible=True, public_consented_at=timezone.now())
    PublicHandle.objects.create(user=user, profile=profile, handle="cover.maker", changed_at=timezone.now())
    client = APIClient()
    assert client.get("/share/pages/cover.maker/").status_code == 200
    assert client.get("/share/pages/cover.maker/cover/").status_code == 404


@pytest.mark.parametrize("withdrawal", ["unpublished", "site_disabled", "inherit_cover", "no_cover"])
def test_cover_route_404s_for_non_public_pages_and_non_asset_covers(page_owner, private_store, stored_bytes,
                                                                     settings, monkeypatch, withdrawal):
    space, actor = page_owner
    mode = {"inherit_cover": "inherit", "no_cover": "none"}.get(withdrawal, "asset")
    state, _ = published_cover("makerspace", space, actor, "cover.lab", cover_mode=mode)
    if withdrawal == "unpublished":
        pages.unpublish("makerspace", space.pk, actor=actor, version=state["version"])
    elif withdrawal == "site_disabled":
        space.public_site_enabled = False
        space.save(update_fields=["public_site_enabled"])
    def no_storage(*args, **kwargs):
        pytest.fail("Refused cover requests must not read private storage")
    monkeypatch.setattr("apps.evidence.storage.object_size", no_storage)
    settings.API_CLIENT_AUTH_REQUIRED = True
    assert APIClient().get("/share/pages/cover.lab/cover/").status_code == 404


def test_inherit_cover_keeps_public_image_url(page_owner, private_store, settings):
    space, actor = page_owner
    space.cover_image_key = "public/makerspaces/cover.webp"
    space.save(update_fields=["cover_image_key"])
    published_cover("makerspace", space, actor, "cover.lab", cover_mode="inherit")
    image = og_image(APIClient(), "cover.lab")
    assert image and "/share/pages/" not in image


def test_editor_image_reads_storage_outside_the_page_lock(page_owner, private_store, monkeypatch):
    from apps.evidence import storage
    space, actor = page_owner
    _, asset_id = published_cover("makerspace", space, actor, "cover.lab")
    reads = []
    def object_size(key):
        assert not connection.in_atomic_block, "storage read happened inside the locking transaction"
        reads.append(key)
        return 4
    monkeypatch.setattr(storage, "object_size", object_size)
    monkeypatch.setattr(storage, "_client", lambda: SimpleNamespace(get_object=lambda **kw: {"Body": BytesIO(b"webp")}))
    url = reverse("makerspace-public-page-asset", kwargs={"pk": space.pk, "asset_id": asset_id})
    response = client_for(actor).get(url)
    assert response.status_code == 200 and response.content == b"webp" and reads
    assert "no-store" in response["Cache-Control"]

import pytest
from rest_framework.exceptions import NotFound
from rest_framework.test import APIRequestFactory
from apps.makerspaces import public_page_services as pages
from apps.makerspaces.public_page_access import public_page, resolve_handle
from apps.makerspaces.models_public_pages import MakerspacePublicPageAsset
from apps.makerspaces.public_page_assets import public_asset_ids
from apps.makerspaces.public_page_asset_views import PublicPageAssetView
from apps.organizations.models import Organization, OrganizationMembership
from apps.organizations.governance import MANAGE_ORGANIZATION_PROFILE
from tests.events.ticketing_helpers import account

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("withdrawal", ["unpublish", "release_handle", "site_off", "archived", "importing"])
def test_live_withdrawal_blocks_page_resolver_and_private_assets(page_owner, withdrawal, monkeypatch):
    from django.http import HttpResponse
    from django.utils import timezone
    owner, actor = page_owner
    state = pages.change_handle("makerspace", owner.pk, actor=actor, version=0, handle="withdraw.lab")
    page = owner.public_page
    asset = MakerspacePublicPageAsset.objects.create(page=page,
        object_key=f"pages/makerspaces/{owner.pk}/{page.pk}/portrait.webp", size_bytes=10, alt_text="Portrait")
    doc = state["document"]
    doc["cover_mode"], doc["cover_asset_id"] = "asset", asset.pk
    state = pages.save("makerspace", owner.pk, actor=actor, version=state["version"], document=doc)
    state = pages.publish("makerspace", owner.pk, actor=actor, version=state["version"], draft_revision_id=state["draft_revision_id"])
    request = APIRequestFactory().get("/", HTTP_HOST="testserver")
    page = public_page("makerspace", owner, request)
    assert public_asset_ids(page.published_revision) == {asset.pk}
    calls = []
    monkeypatch.setattr("apps.makerspaces.public_page_asset_views.private_image_response",
                        lambda key: calls.append(key) or HttpResponse(b"image"))
    view = PublicPageAssetView.as_view()
    assert view(request, makerspace_slug=owner.slug, asset_id=asset.pk).status_code == 200
    assert len(calls) == 1
    if withdrawal == "unpublish":
        pages.unpublish("makerspace", owner.pk, actor=actor, version=state["version"])
    elif withdrawal == "release_handle":
        pages.change_handle("makerspace", owner.pk, actor=actor, version=state["version"], release=True)
    else:
        field, value = {"site_off": ("public_site_enabled", False), "archived": ("archived_at", timezone.now()),
                        "importing": ("lifecycle_state", "importing")}[withdrawal]
        setattr(owner, field, value)
        owner.save(update_fields=[field])
    owner.refresh_from_db()
    with pytest.raises(NotFound):
        public_page("makerspace", owner, request)
    with pytest.raises(NotFound):
        resolve_handle("withdraw.lab", request)
    assert view(APIRequestFactory().get("/"), makerspace_slug=owner.slug, asset_id=asset.pk).status_code == 404
    assert len(calls) == 1


@pytest.mark.parametrize("withdrawal", ["outer_consent", "inactive", "builder_unpublish"])
def test_global_organization_withdrawal_rechecks_outer_consent_and_publication(withdrawal, settings):
    settings.INFRA_HOSTS = ["testserver"]
    user = account("page-governor")
    org = Organization.objects.create(name="Organization", slug="withdraw-org")
    OrganizationMembership.objects.create(organization=org, user=user,
        governance_actions=[MANAGE_ORGANIZATION_PROFILE])
    state = pages.change_handle("organization", org.pk, actor=user, version=0, handle="withdraw.org")
    state = pages.save("organization", org.pk, actor=user, version=state["version"], document=state["document"])
    state = pages.publish("organization", org.pk, actor=user, version=state["version"], draft_revision_id=state["draft_revision_id"])
    request = APIRequestFactory().get("/")
    org.refresh_from_db()
    assert public_page("organization", org, request)
    if withdrawal == "builder_unpublish":
        pages.unpublish("organization", org.pk, actor=user, version=state["version"])
    else:
        field = "public_profile_enabled" if withdrawal == "outer_consent" else "is_active"
        setattr(org, field, False)
        org.save(update_fields=[field])
    org.refresh_from_db()
    with pytest.raises(NotFound):
        public_page("organization", org, request)
    with pytest.raises(NotFound):
        resolve_handle("withdraw.org", request)

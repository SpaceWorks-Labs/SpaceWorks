"""Global byte ownership survives tenant freezes and rejects raced governors."""
import pytest
from django.db import connection
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from apps.makerspaces import public_page_assets as assets
from apps.makerspaces.models_page_cleanup import PublicPageObjectCleanup as Cleanup
from apps.makerspaces.public_page_asset_cleanup import clean_object
from apps.makerspaces.public_page_errors import PageConflict
from apps.organizations.models import Organization, OrganizationMembership, OrganizationMakerspace
from apps.organizations.models_public_pages import OrganizationPublicPageAsset, OrganizationPublicPageStorage
from apps.organizations.governance import MANAGE_ORGANIZATION_PROFILE
from tests.events.ticketing_helpers import account, event_space
from tests.public_pages.test_l1_assets import picture, private_store  # noqa: F401
from tests.tenant_migration.source_gate_helpers import close_gate, make_actor

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def governor():
    user = account("asset-governor")
    org = Organization.objects.create(name="Global pictures", slug="global-pictures")
    member = OrganizationMembership.objects.create(organization=org, user=user,
        governance_actions=[MANAGE_ORGANIZATION_PROFILE])
    return org, user, member


def test_governance_revoked_between_upload_reservation_and_finalize_keeps_quota_debt(governor, private_store, monkeypatch):
    org, user, membership = governor
    put = assets.website_assets._put
    def revoke(key, data, mime):
        assert not connection.in_atomic_block
        put(key, data, mime)
        if not key.startswith("staging/"):
            OrganizationMembership.objects.filter(pk=membership.pk).update(status="suspended")
    monkeypatch.setattr(assets.website_assets, "_put", revoke)
    with pytest.raises((NotFound, PermissionDenied)):
        assets.upload("organization", org.pk, actor=user, version=0, file=picture(), alt_text="Workshop")
    assert not OrganizationPublicPageAsset.objects.exists()
    job = Cleanup.objects.get(owner_kind="organization")
    assert OrganizationPublicPageStorage.objects.get(organization=org).used_bytes == job.size_bytes
    assert clean_object(job.pk)
    assert OrganizationPublicPageStorage.objects.get(organization=org).used_bytes == 0
    assert not private_store[0]


def test_linked_tenant_freeze_cannot_freeze_global_upload(governor, private_store, monkeypatch):
    org, user, _ = governor
    space = event_space("frozen-global-link")
    OrganizationMakerspace.objects.create(organization=org, makerspace=space, relationship="affiliate")
    platform = make_actor("global-upload-freeze")
    put = assets.website_assets._put
    def freeze(key, data, mime):
        put(key, data, mime)
        if not key.startswith("staging/"):
            close_gate(space, platform)
    monkeypatch.setattr(assets.website_assets, "_put", freeze)
    result = assets.upload("organization", org.pk, actor=user, version=0, file=picture(), alt_text="Workshop")
    asset = OrganizationPublicPageAsset.objects.get(pk=result["asset"]["id"])
    assert asset.page.organization_id == org.pk
    assert asset.object_key.startswith(f"pages/organizations/{org.pk}/")
    space.refresh_from_db()
    assert space.storage_bytes_used == 0


def test_quota_refusal_precedes_storage_io_and_durable_reservation(governor, private_store):
    org, user, _ = governor
    OrganizationPublicPageStorage.objects.create(organization=org, used_bytes=100_000_000)
    with pytest.raises(ValidationError):
        assets.upload("organization", org.pk, actor=user, version=0, file=picture(), alt_text="Workshop")
    assert not private_store[0] and not Cleanup.objects.exists()


def test_cleanup_claim_prevents_a_late_upload_finalize(governor, private_store, monkeypatch):
    from django.utils import timezone
    org, user, _ = governor
    put = assets.website_assets._put
    def expire(key, data, mime):
        put(key, data, mime)
        if not key.startswith("staging/"):
            job = Cleanup.objects.get(object_key=key)
            Cleanup.objects.filter(pk=job.pk).update(due_at=timezone.now())
            assert clean_object(job.pk)
    monkeypatch.setattr(assets.website_assets, "_put", expire)
    with pytest.raises(PageConflict):
        assets.upload("organization", org.pk, actor=user, version=0, file=picture(), alt_text="Workshop")
    assert not OrganizationPublicPageAsset.objects.exists()
    assert not private_store[0]
    assert OrganizationPublicPageStorage.objects.get(organization=org).used_bytes == 0

"""Decorated public/private signatures keep capacity until the URL really expires."""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.evidence.models import EvidencePhoto
from apps.inventory import public_image_storage
from apps.machines import storage as documents
from apps.makerspaces.models import StorageQuotaReservation
from apps.makerspaces.storage_reservation_cleanup import cleanup
from apps.makerspaces.storage_reservations import reserved_bytes
from apps.storage_capabilities import presigning
from tests.cloud.storage.test_contracts import contract
from tests.return_helpers import make_space

pytestmark = [pytest.mark.django_db, pytest.mark.area_inventory, pytest.mark.area_machines]


def world(settings, monkeypatch, public):
    settings.MANAGED_PLANS_ENABLED = False
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    settings.STORAGE_CAPABILITIES_FILE = ""
    settings.STORAGE_PRESIGN_METHOD = "auto"
    settings.PUBLIC_IMAGE_MAX_BYTES = settings.MACHINE_DOC_MAX_BYTES = 10
    settings.PUBLIC_IMAGE_URL_TTL_SECONDS, settings.EVIDENCE_URL_TTL_SECONDS = 120, 300
    space = make_space("cx7-r4-initial-signature")
    module = public_image_storage if public else documents
    clock = SimpleNamespace(now=timezone.now())
    monkeypatch.setattr(timezone, "now", lambda: clock.now)
    client = Mock(meta=SimpleNamespace(endpoint_url="https://storage.test"))
    monkeypatch.setattr(module, "_client", lambda: client)
    monkeypatch.setattr(module, "_public_client", lambda: client)
    value = contract(max_object_bytes=10, presign_methods=frozenset({"post"}))
    monkeypatch.setattr(presigning, "capabilities_for", lambda *a, **kw: value)
    monkeypatch.setattr(presigning, "verified_state", lambda *a: SimpleNamespace(facts={"presign_methods": ["post"]}))
    def sign(**kwargs):
        clock.now += timedelta(seconds=7)
        return {"url": "https://storage.test/upload", "fields": {}}
    client.generate_presigned_post.side_effect = sign
    key = f"items/{space.pk}/initial.png" if public else f"machines/{space.pk}/initial.pdf"
    return space, module, clock, client, key


@pytest.mark.parametrize("public", [True, False])
@pytest.mark.parametrize("exact", [None, 4])
def test_first_decorated_signature_retains_exact_debt_at_the_former_expiry(settings, monkeypatch, public, exact):
    space, module, clock, client, key = world(settings, monkeypatch, public)
    ttl = settings.PUBLIC_IMAGE_URL_TTL_SECONDS if public else settings.EVIDENCE_URL_TTL_SECONDS
    former_expiry = clock.now + timedelta(seconds=ttl)
    mime = "image/png" if public else "application/pdf"
    audits = list(AuditLog.objects.filter(makerspace=space).values())
    response = module.presigned_upload(key, mime, exact_bytes=exact)
    assert response["url"] == "https://storage.test/upload"
    row = StorageQuotaReservation.objects.get(makerspace=space)
    assert (row.size_bytes, row.expires_at, row.converted, row.cleaning, row.released) == (
        exact or 10, former_expiry + timedelta(seconds=7), False, False, False)
    bucket = settings.PUBLIC_IMAGE_BUCKET if public else settings.AWS_STORAGE_BUCKET_NAME
    assert (row.bucket, row.final_bucket, row.object_key, row.staging_key) == (bucket, bucket, key, "staging/" + key)
    client.generate_presigned_post.assert_called_once_with(
        Bucket=bucket, Key=row.staging_key, Fields={"Content-Type": mime},
        Conditions=[{"Content-Type": mime}, ["content-length-range", 1, exact or 10]], ExpiresIn=ttl)
    client.generate_presigned_url.assert_not_called()
    before = list(StorageQuotaReservation.objects.filter(pk=row.pk).values())
    deletion = Mock()
    monkeypatch.setattr("apps.object_storage.delete_all_versions", deletion)
    assert cleanup(row.pk, now=former_expiry) is False
    deletion.assert_not_called()
    assert list(StorageQuotaReservation.objects.filter(pk=row.pk).values()) == before
    assert reserved_bytes(space) == (exact or 10)
    assert list(AuditLog.objects.filter(makerspace=space).values()) == audits
    assert EvidencePhoto.objects.filter(makerspace=space).count() == 0


@pytest.mark.parametrize("public", [True, False])
def test_failed_first_signing_rolls_back_admission(settings, monkeypatch, public):
    space, module, _, client, key = world(settings, monkeypatch, public)
    client.generate_presigned_post.side_effect = ClientError({"Error": {"Code": "AccessDenied"}}, "presign")
    audits = list(AuditLog.objects.filter(makerspace=space).values())
    with pytest.raises(module.StorageUnavailable):
        module.presigned_upload(key, "image/png", exact_bytes=4)
    assert StorageQuotaReservation.objects.filter(makerspace=space).count() == 0
    assert reserved_bytes(space) == 0
    assert list(AuditLog.objects.filter(makerspace=space).values()) == audits


def test_account_imagery_keeps_its_exemption_after_slow_signing(settings, monkeypatch):
    space, module, _, _, _ = world(settings, monkeypatch, True)
    result = module.presigned_upload(f"account/{space.pk}/face.png", "image/png", exact_bytes=4)
    assert result["url"] == "https://storage.test/upload"
    assert StorageQuotaReservation.objects.filter(makerspace=space).count() == 0
    assert reserved_bytes(space) == 0


def test_member_photo_signer_retains_its_first_authorization_horizon(settings, monkeypatch):
    from apps.evidence import storage
    space, _, clock, client, _ = world(settings, monkeypatch, False)
    monkeypatch.setattr(storage, "_client", lambda: client)
    monkeypatch.setattr(storage, "_public_client", lambda: client)
    former_expiry = clock.now + timedelta(seconds=300)
    key = f"member-cards/{space.pk}/first.png"
    result = storage.presigned_upload(key, "image/png", max_bytes=4, exact_bytes=4)
    assert result["url"] == "https://storage.test/upload"
    row = StorageQuotaReservation.objects.get(makerspace=space)
    assert (row.object_key, row.size_bytes, row.expires_at, row.converted, row.cleaning, row.released) == (
        key, 4, former_expiry + timedelta(seconds=7), False, False, False)
    client.generate_presigned_post.assert_called_once_with(
        Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key="staging/" + key,
        Fields={"Content-Type": "image/png"},
        Conditions=[{"Content-Type": "image/png"}, ["content-length-range", 1, 4]], ExpiresIn=300)
    deletion = Mock()
    monkeypatch.setattr("apps.object_storage.delete_all_versions", deletion)
    assert cleanup(row.pk, now=former_expiry) is False
    deletion.assert_not_called()
    assert reserved_bytes(space) == 4

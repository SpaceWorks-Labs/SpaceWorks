"""Legacy wrappers enforce bounds before providers accept any object bytes (540)."""
import importlib
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4
from xml.etree import ElementTree

import pytest
import requests
from botocore.exceptions import ClientError
from rest_framework.exceptions import APIException

from apps.audit.models import AuditLog
from apps.evidence import storage
from apps.makerspaces.models import Makerspace, StorageQuotaReservation
from tests.return_helpers import make_space

pytestmark = [pytest.mark.django_db, pytest.mark.area_inventory, pytest.mark.area_bookings,
              pytest.mark.area_machines, pytest.mark.area_machine_service]

WRAPPERS = [
    ("apps.inventory.public_image_storage", "items", (), True),
    ("apps.bookings.storage", "spaces", (), True),
    ("apps.machines.storage", "machines", (), False),
    ("apps.machines.service_storage", "machine", (7,), False),
    ("apps.maintenance.repairs.storage", "repairs", (), False),
    ("apps.maintenance.storage", "machines", (), False),
    ("apps.procurement.storage", "procurement", (), False),
    ("apps.warranty.storage", "warranty", (), False),
]


def world(module, prefix, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    settings.STORAGE_CAPABILITIES_FILE = ""
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    settings.SPACEWORKS_DEPLOYMENT_MODE = "host"
    for name in ("PUBLIC_IMAGE_MAX_BYTES", "MACHINE_DOC_MAX_BYTES", "EVIDENCE_MAX_BYTES",
                 "PROCUREMENT_RECEIPT_MAX_BYTES", "WARRANTY_DOC_MAX_BYTES"):
        setattr(settings, name, 7)
    space = make_space("r2-legacy-bound")
    space.resource_limit_overrides = {"storage": 7, "storage_public_images_bytes": 7}
    space.save(update_fields=["resource_limit_overrides"])
    key = f"{prefix}/{space.pk}/{uuid4().hex}.png"
    target = importlib.import_module(module)
    provider = Mock(meta=SimpleNamespace(endpoint_url="https://storage.test"))
    provider.generate_presigned_post.return_value = {"url": "https://storage.test/post", "fields": {"key": "staging/" + key}}
    provider.generate_presigned_url.return_value = "https://storage.test/put"
    monkeypatch.setattr(target, "_public_client", lambda: provider)
    monkeypatch.setattr(target, "_client", lambda: provider)
    return space, key, target, provider


def invoke(target, key, extra, **kwargs):
    function = target.presign if target.__name__ == "apps.maintenance.repairs.storage" else target.presigned_upload
    return function(key, "image/png", *extra, **kwargs)


def snapshot(space):
    return (list(StorageQuotaReservation.objects.order_by("pk").values()),
            list(AuditLog.objects.order_by("pk").values()),
            Makerspace.objects.get(pk=space.pk).storage_bytes_used)


@pytest.mark.parametrize("module,prefix,extra,public", WRAPPERS)
def test_legacy_post_omission_reserves_and_enforces_the_whole_domain_ceiling(module, prefix, extra, public, settings, monkeypatch):
    space, key, target, provider = world(module, prefix, settings, monkeypatch)
    settings.STORAGE_PRESIGN_METHOD = "post"
    invoke(target, key, extra)
    assert StorageQuotaReservation.objects.get(object_key=key).size_bytes == 7
    provider.generate_presigned_url.assert_not_called()
    provider.generate_presigned_post.assert_called_once_with(
        Bucket=settings.PUBLIC_IMAGE_BUCKET if public else settings.AWS_STORAGE_BUCKET_NAME,
        Key="staging/" + key, Fields={"Content-Type": "image/png"},
        Conditions=[{"Content-Type": "image/png"}, ["content-length-range", 1, 7]],
        ExpiresIn=settings.PUBLIC_IMAGE_URL_TTL_SECONDS if public else settings.EVIDENCE_URL_TTL_SECONDS,
    )


@pytest.mark.parametrize("module,prefix,extra,public", WRAPPERS)
def test_legacy_put_with_size_reserves_and_signs_exact_bytes(module, prefix, extra, public, settings, monkeypatch):
    space, key, target, provider = world(module, prefix, settings, monkeypatch)
    settings.STORAGE_PRESIGN_METHOD = "put"
    result = invoke(target, key, extra, exact_bytes=4)
    assert StorageQuotaReservation.objects.get(object_key=key).size_bytes == 4
    assert result["headers"] == {"Content-Type": "image/png", "Content-Length": "4"}
    provider.generate_presigned_url.assert_called_once_with("put_object", Params={
        "Bucket": settings.PUBLIC_IMAGE_BUCKET if public else settings.AWS_STORAGE_BUCKET_NAME,
        "Key": "staging/" + key, "ContentType": "image/png", "ContentLength": 4,
    }, ExpiresIn=settings.PUBLIC_IMAGE_URL_TTL_SECONDS if public else settings.EVIDENCE_URL_TTL_SECONDS)
    provider.generate_presigned_post.assert_not_called()


@pytest.mark.parametrize("module,prefix,extra,public", WRAPPERS)
@pytest.mark.parametrize("size,code", [(8, "upload_limit"), (None, "upload_size_required")])
def test_legacy_put_refusal_leaves_no_domain_debt_audit_or_authorization(module, prefix, extra, public, size, code, settings, monkeypatch):
    space, key, target, provider = world(module, prefix, settings, monkeypatch)
    settings.STORAGE_PRESIGN_METHOD = "put"
    before = snapshot(space)
    with pytest.raises(APIException) as refused:
        invoke(target, key, extra, **({"exact_bytes": size} if size is not None else {}))
    assert (refused.value.status_code, str(refused.value.detail["code"])) == (400, code)
    assert snapshot(space) == before
    provider.generate_presigned_url.assert_not_called()
    provider.generate_presigned_post.assert_not_called()


@pytest.mark.parametrize("module,prefix,extra,public", WRAPPERS[4:])
def test_four_legacy_put_wrappers_reject_provider_oversize_before_any_object_is_accepted(module, prefix, extra, public, settings, monkeypatch):
    space, key, target, _ = world(module, prefix, settings, monkeypatch)
    settings.STORAGE_PRESIGN_METHOD = "put"
    provider = storage._s3_client(settings.AWS_S3_ENDPOINT_URL)
    monkeypatch.setattr(target, "_client", lambda: provider)
    monkeypatch.setattr(target, "_public_client", lambda: provider)
    signed = invoke(target, key, extra, exact_bytes=7)
    before = snapshot(space)
    bucket, staged = settings.AWS_STORAGE_BUCKET_NAME, "staging/" + key
    try:
        refused = requests.put(signed["url"], data=b"12345678", headers={"Content-Type": "image/png"}, timeout=20)
        assert refused.status_code == 403
        assert ElementTree.fromstring(refused.content).findtext("Code") == "SignatureDoesNotMatch"
        with pytest.raises(ClientError) as absent:
            provider.head_object(Bucket=bucket, Key=staged)
        assert absent.value.response["ResponseMetadata"]["HTTPStatusCode"] == 404
        assert absent.value.response["Error"]["Code"] == "404"
        assert snapshot(space) == before
        accepted = requests.put(signed["url"], data=b"1234567", headers=signed["headers"], timeout=20)
        assert accepted.status_code == 200
        assert provider.head_object(Bucket=bucket, Key=staged)["ContentLength"] == 7
        assert snapshot(space) == before
    finally:
        from apps.object_storage import delete_all_versions
        assert delete_all_versions(provider, bucket=bucket, key=staged).absence_confirmed is True

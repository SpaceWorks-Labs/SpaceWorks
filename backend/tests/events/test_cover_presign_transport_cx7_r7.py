"""Decision 540: event and series covers use only proven, byte-bounded policies."""
from types import SimpleNamespace

import pytest

from apps.audit.models import AuditLog
from apps.makerspaces.models import StorageQuotaReservation
from apps.storage_capabilities import presigning
from tests.cloud.storage.test_contracts import contract
from tests.events.test_cover_reservations_cx7_r1 import world

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_events]


def configured_world(kind, method, settings, monkeypatch):
    w = world(kind, settings, monkeypatch)
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    settings.SPACEWORKS_DEPLOYMENT_MODE = "host"
    settings.STORAGE_CAPABILITIES_FILE = "proven-cover-transport"
    settings.STORAGE_PRESIGN_METHOD = "auto"
    settings.PUBLIC_IMAGE_MAX_BYTES = 8
    methods = frozenset({"put", "post"}) if method == "post" else frozenset({"put"})
    value = contract(presign_methods=methods, max_object_bytes=8)
    monkeypatch.setattr(presigning, "capabilities_for", lambda *a, **kw: value)
    monkeypatch.setattr(presigning, "verified_state", lambda *a: SimpleNamespace(
        facts={"presign_methods": sorted(methods)}))
    w[-1].policies.clear()
    return w


def snapshot():
    return (list(StorageQuotaReservation.objects.order_by("pk").values()),
            list(AuditLog.objects.order_by("pk").values()))


@pytest.mark.parametrize("kind", ["event", "series"])
@pytest.mark.parametrize("method,size", [("put", 4), ("put", 8), ("post", 4), ("post", None)])
def test_proven_cover_transport_binds_declared_size_or_post_ceiling(kind, method, size, settings, monkeypatch):
    space, owner, api, url, _, _, objects = configured_world(kind, method, settings, monkeypatch)
    body = {"filename": "cover.png", "content_type": "image/png"}
    response = api.post(url, {**body, **({"size": size} if size is not None else {})}, format="json")
    assert response.status_code == 201, response.data
    key = response.data["object_key"]
    row = StorageQuotaReservation.objects.get(object_key=key)
    maximum = 8 if size is None else size
    assert (row.size_bytes, row.converted, row.released) == (maximum, False, False)
    assert (row.bucket, row.staging_key) == (settings.AWS_STORAGE_BUCKET_NAME, "staging/public-images/" + key)
    if method == "put":
        assert response.data["method"] == "PUT"
        assert response.data["headers"] == {"Content-Type": "image/png", "Content-Length": str(size)}
        assert objects.policies == [("put", {"Params": {"Bucket": row.bucket, "Key": row.staging_key,
            "ContentType": "image/png", "ContentLength": size}, "ExpiresIn": settings.PUBLIC_IMAGE_URL_TTL_SECONDS})]
    else:
        assert objects.policies == [("post", {"Bucket": row.bucket, "Key": row.staging_key,
            "Fields": {"Content-Type": "image/png"},
            "Conditions": [{"Content-Type": "image/png"}, ["content-length-range", 1, maximum]],
            "ExpiresIn": settings.PUBLIC_IMAGE_URL_TTL_SECONDS})]
    owner.refresh_from_db()
    assert owner.image_key == ""
    assert AuditLog.objects.filter(makerspace=space, action__in=["event.image_updated", "event.series_image_updated"]).count() == 0


@pytest.mark.parametrize("kind", ["event", "series"])
@pytest.mark.parametrize("size,code", [(None, "upload_size_required"), (9, "upload_limit")])
def test_proven_put_only_cover_refuses_missing_or_oversize_declaration(kind, size, code, settings, monkeypatch):
    _, _, api, url, _, _, objects = configured_world(kind, "put", settings, monkeypatch)
    before = snapshot()
    response = api.post(url, {"filename": "cover.png", "content_type": "image/png",
        **({"size": size} if size is not None else {})}, format="json")
    assert (response.status_code, response.data["code"]) == (400, code)
    assert snapshot() == before
    assert objects.policies == []


@pytest.mark.parametrize("kind", ["event", "series"])
@pytest.mark.parametrize("key,status,code", [("upload_bytes", 400, "upload_limit"),
    ("storage", 400, "limit_reached"),
    ("storage_public_images_bytes", 409, "storage_public_images_bytes_quota_reached")])
def test_cover_declaration_respects_each_quota_before_provider_authorization(kind, key, status, code, settings, monkeypatch):
    space, _, api, url, _, _, objects = configured_world(kind, "put", settings, monkeypatch)
    # Retain the first upload's byte debt, then leave exactly three bytes free.
    used = sum(StorageQuotaReservation.objects.filter(makerspace=space).values_list("size_bytes", flat=True))
    space.resource_limit_overrides = {key: 3 if key == "upload_bytes" else used + 3}
    space.save(update_fields=["resource_limit_overrides"])
    before = snapshot()
    response = api.post(url, {"filename": "cover.png", "content_type": "image/png", "size": 4}, format="json")
    assert (response.status_code, response.data["code"]) == (status, code)
    assert snapshot() == before
    assert objects.policies == []

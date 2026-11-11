import threading
from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError
from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection

from apps.evidence import storage as evidence_storage
from apps.evidence.finalization import charge_storage_once
from apps.evidence.models import EvidencePhoto, EvidenceUploadFinalization
from apps.inventory import public_image_storage
from apps.makerspaces.models import Makerspace
from tests.p3_review8.conftest import image_store, png  # noqa: F401


def _photo(slug="post-finalize"):
    makerspace = Makerspace.objects.create(name=slug, slug=slug)
    uploader = get_user_model().objects.create_user(username=f"{slug}-uploader")
    return EvidencePhoto.objects.create(
        makerspace=makerspace,
        evidence_type=EvidencePhoto.EvidenceType.ISSUE,
        object_key=f"evidence/{makerspace.id}/issue/object",
        uploaded_by=uploader,
    )


def _fake_evidence_store(monkeypatch, objects):
    copied = []

    def validate(key):
        data = objects.get(key)
        if data is None:
            raise evidence_storage.EvidenceObjectValidationError("missing", "missing")
        return evidence_storage.EvidenceValidationResult(
            size=len(data), content_type="image/png"
        )

    def copy(source, destination):
        copied.append((source, destination))
        objects[destination] = objects[source]

    monkeypatch.setattr(evidence_storage, "validate_evidence_object", validate)
    monkeypatch.setattr(evidence_storage, "copy_object", copy)
    monkeypatch.setattr(evidence_storage, "delete_object", objects.pop)
    return copied


@pytest.mark.django_db
def test_post_presign_targets_staging_and_replay_cannot_replace_final(
    monkeypatch, settings, django_capture_on_commit_callbacks
):
    settings.STORAGE_PRESIGN_METHOD = "post"
    photo = _photo()

    class FakePublicClient:
        def generate_presigned_post(self, *, Bucket, Key, Fields, Conditions, ExpiresIn):
            assert Bucket == settings.AWS_STORAGE_BUCKET_NAME
            assert Key == evidence_storage.staging_key(photo.object_key)
            assert Fields == {"Content-Type": "image/png"}
            assert {"Content-Type": "image/png"} in Conditions
            assert ["content-length-range", 1, settings.EVIDENCE_MAX_BYTES] in Conditions
            assert ExpiresIn == settings.EVIDENCE_URL_TTL_SECONDS
            return {"url": "http://minio/upload", "fields": {"key": Key, **Fields}}

    monkeypatch.setattr(evidence_storage, "_public_client", lambda: FakePublicClient())
    upload = evidence_storage.presigned_upload(photo.object_key, "image/png")
    assert upload["fields"]["key"] != photo.object_key

    objects = {upload["fields"]["key"]: b"original-image"}
    copied = _fake_evidence_store(monkeypatch, objects)
    first = evidence_storage.finalize_upload(photo, max_bytes=500)

    assert first.size == len(b"original-image")
    assert objects == {photo.object_key: b"original-image"}
    assert copied == [(evidence_storage.staging_key(photo.object_key), photo.object_key)]

    # The still-valid POST can only recreate staging. Idempotent finalization cleans
    # that replay and never copies it over the accepted final object.
    objects[upload["fields"]["key"]] = b"replacement-image"
    with django_capture_on_commit_callbacks(execute=True):
        second = evidence_storage.finalize_upload(photo, max_bytes=500)

    assert second == first
    assert objects == {photo.object_key: b"original-image"}
    assert len(copied) == 1
    state = EvidenceUploadFinalization.objects.get(evidence=photo)
    assert state.status == EvidenceUploadFinalization.Status.FINALIZED


@pytest.mark.django_db(transaction=True)
def test_concurrent_post_finalization_promotes_exactly_once(monkeypatch, settings):
    settings.STORAGE_PRESIGN_METHOD = "post"
    photo = _photo("post-concurrent")
    staged_key = evidence_storage.staging_key(photo.object_key)
    objects = {staged_key: b"concurrent-image"}
    objects_lock = threading.Lock()
    copy_started = threading.Event()
    contender_checked = threading.Event()
    release_copy = threading.Event()
    copied = []

    def validate(key):
        with objects_lock:
            data = objects.get(key)
        if data is None:
            if threading.current_thread().name == "contender" and key == photo.object_key:
                contender_checked.set()
            raise evidence_storage.EvidenceObjectValidationError("missing", "missing")
        return evidence_storage.EvidenceValidationResult(
            size=len(data), content_type="image/png"
        )

    def copy(source, destination):
        assert connection.in_atomic_block is False
        copied.append((source, destination))
        copy_started.set()
        assert release_copy.wait(timeout=2)
        with objects_lock:
            objects[destination] = objects[source]

    def delete(key):
        with objects_lock:
            objects.pop(key, None)

    monkeypatch.setattr(evidence_storage, "validate_evidence_object", validate)
    monkeypatch.setattr(evidence_storage, "copy_object", copy)
    monkeypatch.setattr(evidence_storage, "delete_object", delete)
    results = []
    errors = []

    def run():
        close_old_connections()
        try:
            current = EvidencePhoto.objects.get(pk=photo.pk)
            results.append(evidence_storage.finalize_upload(current, max_bytes=500))
        except Exception as exc:  # pragma: no cover - asserted below
            errors.append(exc)
        finally:
            close_old_connections()

    owner = threading.Thread(target=run, name="owner")
    contender = threading.Thread(target=run, name="contender")
    owner.start()
    assert copy_started.wait(timeout=2)
    contender.start()
    assert contender_checked.wait(timeout=2)
    release_copy.set()
    owner.join(timeout=3)
    contender.join(timeout=3)

    assert errors == []
    assert len(results) == 2
    assert copied == [(staged_key, photo.object_key)]
    assert objects == {photo.object_key: b"concurrent-image"}


@pytest.mark.django_db
def test_put_evidence_quota_is_charged_once(monkeypatch, settings):
    settings.STORAGE_PRESIGN_METHOD = "put"
    photo = _photo("put-quota-once")
    EvidenceUploadFinalization.objects.create(
        evidence=photo,
        status=EvidenceUploadFinalization.Status.FINALIZED,
        size_bytes=321,
        content_type="image/png",
    )
    add_storage = Mock()
    monkeypatch.setattr("apps.makerspaces.limits.add_storage", add_storage)

    charge_storage_once(photo, 321)
    charge_storage_once(photo, 321)

    add_storage.assert_called_once_with(photo.makerspace, 321)


@pytest.mark.parametrize("method", ["post", "put"])
@pytest.mark.parametrize("transient_key", ["staging", "final"])
def test_public_image_post_finalize_retries_transient_missing_object(
    monkeypatch, settings, image_store, method, transient_key,
):
    settings.STORAGE_PRESIGN_METHOD = method
    final_key = "printers/1/photo.png"
    staged = public_image_storage.staging_key(final_key)
    data = png()
    image_store.objects[staged] = (data, "image/png")
    attempts = []
    missed = False
    original_get = image_store.get_object
    target = staged if transient_key == "staging" else final_key

    def get_object(**kwargs):
        nonlocal missed
        key = kwargs["Key"]
        attempts.append(key)
        if key == target and not missed and (key == staged or image_store.writes):
            missed = True
            raise ClientError({"Error": {"Code": "NoSuchKey"},
                               "ResponseMetadata": {"HTTPStatusCode": 404}}, "GetObject")
        return original_get(**kwargs)

    monkeypatch.setattr(image_store, "get_object", get_object)
    monkeypatch.setattr(public_image_storage.time, "sleep", lambda delay: None)

    result = public_image_storage.finalize_upload(final_key)

    assert result.status == "ok"
    assert result.size == len(data)
    assert attempts == ([final_key, staged, staged, final_key] if transient_key == "staging"
                        else [final_key, staged, final_key, final_key])
    assert image_store.objects == {final_key: (data, "image/png")}
    assert image_store.writes == [final_key]


@pytest.mark.parametrize("method", ["post", "put"])
@pytest.mark.parametrize("payload,status", [
    (png(), "ok"), (b"", "empty"), (b"x" * 501, "too_large"), (None, "missing"),
], ids=["valid", "empty", "oversized", "missing"])
def test_public_image_finalize_uses_size_not_exists(
    monkeypatch, settings, image_store, method, payload, status,
):
    settings.STORAGE_PRESIGN_METHOD = method
    settings.PUBLIC_IMAGE_MAX_BYTES = 500
    final_key = "items/1/object.png"
    staged = public_image_storage.staging_key(final_key)
    if payload is not None:
        image_store.objects[staged] = (payload, "image/png")

    _block_object_exists(monkeypatch, public_image_storage)
    sleeps = []
    monkeypatch.setattr(public_image_storage.time, "sleep", sleeps.append)

    result = public_image_storage.finalize_upload(final_key)

    assert result.status == status
    # Finalize sizes the validated snapshot, never a boolean existence result.
    assert result.size == (len(payload) if payload is not None else None)
    assert image_store.objects == ({final_key: (payload, "image/png")} if status == "ok" else {})
    assert image_store.writes == ([final_key] if status == "ok" else [])
    assert len(sleeps) == (9 if status == "missing" else 0)

def test_evidence_presigned_upload_put_mode_signs_staging_key(monkeypatch, settings):
    settings.STORAGE_PRESIGN_METHOD = "put"

    class FakePublicClient:
        def generate_presigned_url(self, operation, Params, ExpiresIn):
            assert operation == "put_object"
            assert Params == {
                "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
                "Key": "staging/evidence/1/issue/x",
                "ContentType": "image/jpeg",
            }
            assert ExpiresIn == settings.EVIDENCE_URL_TTL_SECONDS
            return "http://minio/evidence-put"

    monkeypatch.setattr(
        "apps.evidence.storage._public_client",
        lambda: FakePublicClient(),
    )

    upload = evidence_storage.presigned_upload("evidence/1/issue/x", "image/jpeg")

    assert upload == {
        "url": "http://minio/evidence-put",
        "method": "PUT",
        "headers": {"Content-Type": "image/jpeg"},
    }

def _block_object_exists(monkeypatch, module):
    if hasattr(module, "object_exists"):
        monkeypatch.setattr(
            module,
            "object_exists",
            lambda key: pytest.fail("unexpected object_exists call"),
        )


@pytest.mark.django_db(transaction=True)
def test_completed_replay_cleans_staging_after_domain_commit(monkeypatch):
    from django.db import transaction

    photo = _photo("completed-replay")
    staged = evidence_storage.staging_key(photo.object_key)
    objects = {staged: b"original-image"}
    copied = _fake_evidence_store(monkeypatch, objects)
    first = evidence_storage.finalize_upload(photo, max_bytes=500)
    objects[staged] = b"replayed-image"
    deleted = []

    def delete(key):
        assert not connection.in_atomic_block
        deleted.append(key)
        objects.pop(key, None)

    monkeypatch.setattr(evidence_storage, "delete_object", delete)
    monkeypatch.setattr(evidence_storage, "validate_evidence_object",
                        lambda key: pytest.fail("completed replay revalidated storage"))
    with transaction.atomic():
        assert evidence_storage.finalize_upload(photo, max_bytes=500) == first
        assert deleted == []
    assert deleted == [staged]
    assert objects == {photo.object_key: b"original-image"}
    assert copied == [(staged, photo.object_key)]

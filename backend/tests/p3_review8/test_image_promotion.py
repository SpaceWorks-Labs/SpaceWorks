"""Both public-image backends stage, validate, freeze and size the winning bytes."""
import pytest
from botocore.exceptions import ClientError

from apps.bookings import storage as bookings
from apps.evidence.storage import StorageUnavailable
from apps.inventory import public_image_storage as shared
from .conftest import png


@pytest.fixture(params=[bookings, shared], ids=["booking-gallery-and-cover", "shared-public-images"])
def storage(request):
    return request.param


def test_presign_is_bound_to_staging_mime_and_post_size(storage, image_store, presign_mode, settings):
    key = "event/1/a.png"
    upload = storage.presigned_upload(key, "image/png")
    signed = image_store.signed[-1]
    assert signed["Key"] == storage.staging_key(key)
    if presign_mode == "post":
        assert signed["Fields"]["Content-Type"] == "image/png"
        assert {"Content-Type": "image/png"} in signed["Conditions"]
        assert ["content-length-range", 1, settings.PUBLIC_IMAGE_MAX_BYTES] in signed["Conditions"]
    else:
        assert signed["ContentType"] == "image/png"
        assert upload["headers"] == {"Content-Type": "image/png"}


def test_replayed_presign_cannot_change_final_bytes_or_size(storage, image_store):
    key = "event/1/frozen.png"
    data = png()
    image_store.objects[storage.staging_key(key)] = (data, "image/png")
    result = storage.finalize_upload(key)
    assert result.status == "ok" and result.size == len(data)
    assert storage.staging_key(key) not in image_store.objects
    image_store.objects[storage.staging_key(key)] = (png("blue") + b"extra", "image/png")
    assert storage.finalize_upload(key) == result
    assert image_store.objects[key] == (data, "image/png")
    assert image_store.writes == [key]


@pytest.mark.parametrize("payload,mime,status", [
    (b"", "image/png", "empty"), (b"x" * 1025, "image/png", "too_large"),
    (b"not an image", "image/png", "invalid_image"),
    (png(), "image/jpeg", "invalid_image"), (png(), "application/octet-stream", "invalid_image"),
])
def test_invalid_staging_is_never_promoted(storage, image_store, payload, mime, status):
    key = "member/1/bad.png"
    image_store.objects[storage.staging_key(key)] = (payload, mime)
    assert storage.finalize_upload(key).status == status
    assert key not in image_store.objects and not image_store.writes


def test_missing_upload_is_refused(storage, image_store):
    assert storage.finalize_upload("member/1/missing.png").status == "missing"


def test_extension_must_match_sniffed_type(storage, image_store):
    key = "member/1/wrong.jpg"
    image_store.objects[storage.staging_key(key)] = (png(), "image/png")
    assert storage.finalize_upload(key).status == "invalid_image"
    assert key not in image_store.objects


def test_staging_replaced_during_promotion_uses_validated_snapshot(storage, image_store):
    key = "member/1/race.png"
    original = png()
    image_store.objects[storage.staging_key(key)] = (original, "image/png")
    image_store.before_put = lambda _: image_store.objects.update({storage.staging_key(key): (b"bad", "text/plain")})
    assert storage.finalize_upload(key).size == len(original)
    assert image_store.objects[key] == (original, "image/png")


def test_concurrent_finalizer_keeps_winner_and_returns_its_size(storage, image_store):
    key = "event-series/1/race.png"
    winner = png("blue")
    image_store.objects[storage.staging_key(key)] = (png() + b"other length", "image/png")
    image_store.before_put = lambda final: image_store.objects.update({final: (winner, "image/png")})
    result = storage.finalize_upload(key)
    assert result.status == "ok" and result.size == len(winner)
    assert image_store.objects[key] == (winner, "image/png")
    assert not image_store.writes


def test_storage_failure_is_retryable_and_keeps_staging(storage, image_store, monkeypatch):
    key = "event/1/retry.png"
    image_store.objects[storage.staging_key(key)] = (png(), "image/png")
    def fail(**kwargs):
        raise ClientError({"Error": {"Code": "AccessDenied"}}, "PutObject")
    monkeypatch.setattr(image_store, "put_object", fail)
    with pytest.raises(StorageUnavailable):
        storage.finalize_upload(key)
    assert storage.staging_key(key) in image_store.objects and key not in image_store.objects

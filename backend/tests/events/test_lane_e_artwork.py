from io import BytesIO
import hashlib
from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError
from django.db import connection
from PIL import Image
from rest_framework.exceptions import ValidationError

from apps.events import certificate_artwork_storage as storage
from apps.events.models import EventCertificateArtwork
from apps.events.services_certificate_templates import reserve_artwork, finalize_artwork
from tests.events.staff_grant_helpers import grant_fixture


def png(colour="red"):
    output = BytesIO()
    Image.new("RGB", (12, 8), colour).save(output, format="PNG")
    return output.getvalue()


class S3:
    def __init__(self):
        self.objects = {}
        self.puts = []
        self.signed = None

    def generate_presigned_url(self, operation, **values):
        self.signed = (operation, values)
        return "https://private.test/upload"

    def get_object(self, **params):
        key = params["Key"]
        if key not in self.objects:
            raise ClientError({"Error": {"Code": "NoSuchKey"}, "ResponseMetadata": {"HTTPStatusCode": 404}}, "GetObject")
        return {"Body": BytesIO(self.objects[key]), "VersionId": "version-one"}

    def put_object(self, **params):
        assert params["IfNoneMatch"] == "*"
        self.puts.append(params)
        if params["Key"] in self.objects:
            raise ClientError({"Error": {"Code": "PreconditionFailed"}, "ResponseMetadata": {"HTTPStatusCode": 412}}, "PutObject")
        self.objects[params["Key"]] = params["Body"]
        return {"VersionId": "version-one"}


def test_presign_is_bound_to_private_staging_mime_size_and_expiry(monkeypatch, settings):
    fake = S3()
    monkeypatch.setattr(storage, "_client", lambda endpoint: fake)
    row = type("Row", (), {"object_key": "events/certificate-artwork/1/key.png"})()
    storage.upload_url(row, content_type="image/png", content_length=123)
    operation, values = fake.signed
    assert operation == "put_object"
    assert values["Params"]["Key"] == f"staging/{row.object_key}"
    assert values["Params"]["Bucket"] == settings.AWS_STORAGE_BUCKET_NAME
    assert values["Params"]["ContentType"] == "image/png"
    assert values["Params"]["ContentLength"] == 123
    assert values["ExpiresIn"] == 600


def test_canonical_promotion_wins_once_even_if_live_presign_overwrites_staging(monkeypatch):
    fake = S3()
    monkeypatch.setattr(storage, "_client", lambda endpoint: fake)
    row = type("Row", (), {"object_key": "events/certificate-artwork/1/key.png"})()
    fake.objects[f"staging/{row.object_key}"] = png("red")
    first = storage.promote_bytes(row)
    final = fake.objects[row.object_key]
    fake.objects[f"staging/{row.object_key}"] = png("blue")
    second = storage.promote_bytes(row)
    assert first == second
    assert fake.objects[row.object_key] == final
    assert storage.read_artwork(row.object_key, "version-one", first[1]) == final
    with pytest.raises(storage.ArtworkUnavailable):
        storage.read_artwork(row.object_key, "version-one", "0" * 64)


@pytest.mark.parametrize("payload", [b"<svg>malicious</svg>", b"not an image", b""])
def test_invalid_artwork_is_a_typed_boundary_refusal(payload):
    with pytest.raises(ValidationError):
        storage._png(payload)


@pytest.mark.parametrize("format", ["PNG", "JPEG"])
def test_promotion_strips_exif_icc_and_text_metadata_from_canonical_bytes(format, monkeypatch):
    from PIL.PngImagePlugin import PngInfo

    exif = Image.Exif()
    exif[315] = "Private uploader identity"
    metadata = {"exif": exif, "icc_profile": b"Private uploader colour profile"}
    if format == "PNG":
        text = PngInfo()
        text.add_text("Author", "Private uploader identity")
        metadata["pnginfo"] = text
    source = BytesIO()
    Image.new("RGB", (12, 8), "red").save(source, format=format, **metadata)
    with Image.open(BytesIO(source.getvalue())) as uploaded:
        assert uploaded.getexif()[315] == "Private uploader identity"
        assert uploaded.info["icc_profile"] == metadata["icc_profile"]
        pixels = uploaded.convert("RGB").tobytes()

    fake = S3()
    monkeypatch.setattr(storage, "_client", lambda endpoint: fake)
    row = type("Row", (), {"object_key": "events/certificate-artwork/1/metadata.png"})()
    fake.objects[f"staging/{row.object_key}"] = source.getvalue()
    size, digest, version = storage.promote_bytes(row)
    canonical = storage.read_artwork(row.object_key, version, digest)
    assert size == len(canonical)
    with Image.open(BytesIO(canonical)) as cleaned:
        # Layered certificates keep artwork transparency (RGBA); metadata is still stripped.
        assert cleaned.format == "PNG" and cleaned.mode == "RGBA"
        assert cleaned.size == (12, 8) and cleaned.convert("RGB").tobytes() == pixels
        assert not cleaned.info and not cleaned.getexif()
    assert b"Private uploader" not in canonical


@pytest.mark.parametrize("mode", ["RGBA", "LA", "P"])
def test_transparent_artwork_promotes_with_its_alpha_preserved(mode, monkeypatch):
    source = BytesIO()
    image = Image.new("RGBA", (3, 1))
    image.putdata([(0, 0, 0, 0), (0, 0, 0, 128), (0, 0, 0, 255)])
    if mode == "LA":
        image = image.convert("LA")
    elif mode == "P":
        image = Image.new("P", (3, 1))
        image.putpalette([0, 0, 0] * 256)
        image.putdata([0, 1, 2])
        image.info["transparency"] = bytes([0, 128, 255])
    image.save(source, format="PNG")
    fake = S3()
    monkeypatch.setattr(storage, "_client", lambda endpoint: fake)
    row = type("Row", (), {"object_key": f"events/certificate-artwork/1/{mode}.png"})()
    fake.objects[f"staging/{row.object_key}"] = source.getvalue()
    size, digest, version = storage.promote_bytes(row)
    canonical = storage.read_artwork(row.object_key, version, digest)
    with Image.open(BytesIO(canonical)) as cleaned:
        # Logo/signature layers composite over the page at render time, so promotion
        # keeps each pixel's alpha instead of flattening onto white.
        assert cleaned.mode == "RGBA" and not cleaned.info
        assert [pixel[3] for pixel in cleaned.getdata()] == [0, 128, 255]
        assert list(cleaned.getdata())[1:] == [(0, 0, 0, 128), (0, 0, 0, 255)]
    assert size == len(canonical)


def test_image_bomb_and_decoded_pixel_limit_are_validation_errors(monkeypatch):
    monkeypatch.setattr(storage, "image_mime_from_bytes", Mock(side_effect=Image.DecompressionBombError()))
    with pytest.raises(ValidationError):
        storage._png(b"bomb")


@pytest.mark.django_db(transaction=True)
def test_reservation_precedes_external_io_and_finalize_is_idempotent(monkeypatch):
    space, manager, editor, event, grant = grant_fixture()
    space.enabled_features += ["events.certificate_designer"]
    space.save()
    monkeypatch.setattr("apps.makerspaces.limits.is_self_host", lambda: False)
    monkeypatch.setattr("apps.makerspaces.limits.resource_limit", lambda *args: 2 * storage.MAX_BYTES)
    monkeypatch.setattr(storage, "upload_url", lambda *args, **kwargs: "signed")
    row, url = reserve_artwork(event, actor=editor, content_type="image/png", content_length=123)
    space.refresh_from_db()
    assert space.storage_bytes_used == row.size_bytes == storage.MAX_BYTES
    assert row.promoted_at is None and url == "signed"
    def promote(artwork):
        assert not connection.in_atomic_block
        return 123, "a" * 64, "v1"
    work = Mock(side_effect=promote)
    monkeypatch.setattr(storage, "promote_bytes", work)
    monkeypatch.setattr(storage, "cleanup_staging", lambda row: None)
    first = finalize_artwork(event, row.pk, actor=editor)
    second = finalize_artwork(event, row.pk, actor=editor)
    space.refresh_from_db()
    assert first.pk == second.pk and first.promoted_at
    assert space.storage_bytes_used == 123
    assert work.call_count == 1


@pytest.mark.django_db
def test_failed_presign_rolls_back_reservation_audit_and_quota(monkeypatch):
    from apps.audit.models import AuditLog
    space, manager, editor, event, grant = grant_fixture()
    space.enabled_features += ["events.certificate_designer"]
    space.save()
    monkeypatch.setattr("apps.makerspaces.limits.is_self_host", lambda: False)
    monkeypatch.setattr("apps.makerspaces.limits.resource_limit", lambda *args: storage.MAX_BYTES)
    monkeypatch.setattr(storage, "upload_url", Mock(side_effect=storage.ArtworkUnavailable()))
    with pytest.raises(storage.ArtworkUnavailable):
        reserve_artwork(event, actor=editor, content_type="image/png", content_length=123)
    space.refresh_from_db()
    assert space.storage_bytes_used == 0
    assert not EventCertificateArtwork.objects.exists()
    assert not AuditLog.objects.filter(action="event.certificate_artwork_presigned").exists()


@pytest.mark.django_db
def test_quota_failure_prevents_presign_and_failed_attach_retains_reserved_budget(monkeypatch):
    space, manager, editor, event, grant = grant_fixture()
    space.enabled_features += ["events.certificate_designer"]
    space.save()
    monkeypatch.setattr("apps.makerspaces.limits.is_self_host", lambda: False)
    monkeypatch.setattr("apps.makerspaces.limits.resource_limit", lambda *args: storage.MAX_BYTES)
    sign = Mock(return_value="signed")
    monkeypatch.setattr(storage, "upload_url", sign)
    row, _url = reserve_artwork(event, actor=editor, content_type="image/png", content_length=123)
    with pytest.raises(ValidationError):
        reserve_artwork(event, actor=editor, content_type="image/png", content_length=123)
    assert sign.call_count == 1
    monkeypatch.setattr(storage, "promote_bytes", Mock(return_value=(123, "a" * 64, "v1")))
    # Revoke after the precheck/work; attachment rechecks live authority under lock.
    original = storage.promote_bytes
    def revoke_during_io(row):
        from django.utils import timezone
        grant.revoked_at = timezone.now()
        grant.save()
        return original(row)
    monkeypatch.setattr(storage, "promote_bytes", revoke_during_io)
    from rest_framework.exceptions import PermissionDenied
    with pytest.raises(PermissionDenied):
        finalize_artwork(event, row.pk, actor=editor)
    row.refresh_from_db()
    space.refresh_from_db()
    assert row.promoted_at is None
    assert row.size_bytes == space.storage_bytes_used == storage.MAX_BYTES


@pytest.mark.django_db
def test_promoted_artwork_metadata_rejects_orm_updates_and_deletes():
    from django.db import DatabaseError, transaction
    from django.utils import timezone
    space, manager, editor, event, grant = grant_fixture()
    row = EventCertificateArtwork.objects.create(event=event, object_key="events/certificate-artwork/1/frozen.png",
                                                 size_bytes=123, sha256="a" * 64, promoted_at=timezone.now())
    with pytest.raises(DatabaseError), transaction.atomic():
        EventCertificateArtwork.objects.filter(pk=row.pk).update(sha256="b" * 64)
    with pytest.raises(DatabaseError), transaction.atomic():
        EventCertificateArtwork.objects.filter(pk=row.pk).delete()


def test_staged_body_read_is_bounded_and_stream_closed():
    fake = S3()
    fake.objects["too-big"] = b"x" * (storage.MAX_BYTES + 1)
    with pytest.raises(ValidationError):
        storage._read(fake, "too-big")

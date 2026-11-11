import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.exceptions import ValidationError

from apps.bookings.models import BookableSpace, Booking
from apps.bookings.services_clone import clone_space
from apps.bookings.services_website_assets import upload_asset, delete_asset
from apps.bookings.services_website import save_content
from apps.evidence.storage import StorageUnavailable
from apps.makerspaces import website_assets
from tests.bookings.website_helpers import world, image, memory_storage, section

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("data", [b"<svg onload='alert(1)'/>", b"<html>image</html>", b"", b"x" * 5_000_001])
def test_malicious_type_and_size_refuse_without_row_or_quota(monkeypatch, data):
    w = world()
    objects, _ = memory_storage(monkeypatch)
    w.tenant.refresh_from_db()
    before = w.tenant.storage_bytes_used
    with pytest.raises(ValidationError):
        upload_asset(w.resource, actor=w.actor,
                     file=SimpleUploadedFile("fake.png", data, content_type="image/png"), alt_text="Test")
    assert not w.resource.website_page.assets.exists() and not objects
    w.tenant.refresh_from_db()
    assert w.tenant.storage_bytes_used == before


def test_decompression_bomb_and_animation_refuse():
    from io import BytesIO
    from PIL import Image
    for frames in (1, 2):
        stream = BytesIO()
        if frames == 1:
            Image.new("1", (5000, 5000)).save(stream, format="PNG")
        else:
            Image.new("RGB", (10, 10), "red").save(stream, format="PNG", save_all=True,
                append_images=[Image.new("RGB", (10, 10), "blue")])
        with pytest.raises(ValidationError):
            website_assets.webp(stream.getvalue())


def test_upload_reencode_replacement_and_delete_release_exact_bytes(monkeypatch):
    w = world()
    objects, deleted = memory_storage(monkeypatch)
    first = upload_asset(w.resource, actor=w.actor, file=image(), alt_text="First")
    assert objects[first.object_key][:4] == b"RIFF"
    assert not any(key.startswith("staging/") for key in objects)
    page = w.resource.website_page
    page.sections.update(asset=first)
    replacement = upload_asset(w.resource, actor=w.actor, file=image(), alt_text="Second", replace_id=first.pk)
    assert page.sections.get().asset_id == replacement.pk
    assert first.object_key in deleted and first.object_key not in objects
    w.tenant.refresh_from_db()
    assert w.tenant.storage_bytes_used == replacement.size_bytes
    delete_asset(w.resource, replacement.pk, actor=w.actor)
    w.tenant.refresh_from_db()
    assert w.tenant.storage_bytes_used == 0 and not objects


def test_failed_audit_rolls_back_rows_quota_and_cleans_both_keys(monkeypatch):
    w = world()
    objects, deleted = memory_storage(monkeypatch)
    def fail(*args, **kwargs):
        raise RuntimeError("audit unavailable")
    monkeypatch.setattr("apps.bookings.services_website.record", fail)
    with pytest.raises(RuntimeError):
        upload_asset(w.resource, actor=w.actor, file=image(), alt_text="New")
    assert not objects and not w.resource.website_page.assets.exists()
    w.tenant.refresh_from_db()
    assert w.tenant.storage_bytes_used == 0
    assert len(deleted) >= 2


def test_quota_refusal_and_storage_failure_cleanup(monkeypatch):
    w = world()
    objects, _ = memory_storage(monkeypatch)
    def fail(*args, **kwargs):
        raise ValidationError("Quota exceeded")
    with monkeypatch.context() as patch:
        patch.setattr(website_assets.limits, "add_storage", fail)
        with pytest.raises(ValidationError):
            upload_asset(w.resource, actor=w.actor, file=image(), alt_text="Quota")
    assert not objects
    def fail_put(key, data, mime):
        objects[key] = data
        raise StorageUnavailable()
    monkeypatch.setattr(website_assets, "_put", fail_put)
    with pytest.raises(StorageUnavailable):
        upload_asset(w.resource, actor=w.actor, file=image(), alt_text="Failure")
    assert not objects


def test_clone_independent_assets_unreleased_no_authority_or_history(monkeypatch):
    w = world()
    objects, _ = memory_storage(monkeypatch)
    source = upload_asset(w.resource, actor=w.actor, file=image(), alt_text="Source")
    page = w.resource.website_page
    page.refresh_from_db()
    save_content(w.resource, actor=w.actor, data={"revision": page.revision,
        "sections": [section(asset_id=source.pk)]})
    clone = clone_space(w.resource, actor=w.actor)
    target = clone.website_page
    copied = target.assets.get()
    assert not clone.is_public and not target.released
    assert clone.public_token != w.resource.public_token and copied.object_key != source.object_key
    assert objects[copied.object_key] == objects[source.object_key]
    assert not Booking.objects.filter(space=clone).exists()
    assert not clone.bookingspacestaffgrant_rows.exists()
    delete_asset(clone, copied.pk, actor=w.actor)
    assert source.object_key in objects and copied.object_key not in objects


def test_clone_rejects_forged_ownership_and_rolls_back_new_resource(monkeypatch):
    w = world()
    memory_storage(monkeypatch)
    asset = upload_asset(w.resource, actor=w.actor, file=image(), alt_text="Owned")
    type(asset).objects.filter(pk=asset.pk).update(object_key="bookings/website/999/999/foreign.webp")
    before = BookableSpace.objects.count()
    with pytest.raises(ValidationError):
        clone_space(w.resource, actor=w.actor)
    assert BookableSpace.objects.count() == before


def test_failed_clone_copy_cleans_fresh_keys_and_keeps_source(monkeypatch):
    w = world()
    objects, deleted = memory_storage(monkeypatch)
    source = upload_asset(w.resource, actor=w.actor, file=image(), alt_text="Source")
    before = BookableSpace.objects.count()
    def uncertain_copy(source_key, target_key):
        objects[target_key] = objects[source_key]
        raise StorageUnavailable()
    monkeypatch.setattr(website_assets, "copy_object", uncertain_copy)
    with pytest.raises(StorageUnavailable):
        clone_space(w.resource, actor=w.actor)
    assert set(objects) == {source.object_key}
    assert BookableSpace.objects.count() == before
    assert source.object_key not in deleted


def test_asset_count_limit_and_unowned_replace_id_refuse(monkeypatch):
    from apps.bookings.models_website import BookingResourcePageAsset
    from django.http import Http404
    w = world()
    objects, _ = memory_storage(monkeypatch)
    with pytest.raises(Http404):
        upload_asset(w.resource, actor=w.actor, file=image(), alt_text="Foreign replacement", replace_id=999999)
    for i in range(100):
        BookingResourcePageAsset.objects.create(page=w.resource.website_page,
            object_key=f"bookings/website/{w.tenant.pk}/{w.resource.website_page.pk}/{i}.webp", size_bytes=1, alt_text="Stored")
    with pytest.raises(ValidationError):
        upload_asset(w.resource, actor=w.actor, file=image(), alt_text="Over limit")
    assert not objects

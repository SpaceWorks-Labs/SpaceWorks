"""Place photo gallery writes: presign -> finalize -> attach, caption, reorder, delete.

Authority is the space's `edit_details` permission (Booking Manager, or a resource grant
holding it). Storage I/O (HEAD, sniff, copy) happens before the row lock, the quota is
charged inside it, and a removed photo's bytes and quota are released only after commit.
"""

from django.db import transaction
from django.db.models import Max
from django.shortcuts import get_object_or_404
from rest_framework import serializers

from apps.audit import services as audit
from apps.makerspaces import limits

from . import storage
from .booking_authority import require
from .models import BookableSpace
from .models_gallery import MAX_PHOTOS_PER_SPACE, BookableSpacePhoto


def _locked(space, actor):
    locked = BookableSpace.objects.select_for_update().select_related("makerspace").get(pk=space.pk)
    require(actor, locked, "edit_details")
    if not locked.is_active:
        raise serializers.ValidationError({"space": "Inactive spaces cannot have photos changed."})
    return locked


def require_room(space):
    if not space.is_active:
        raise serializers.ValidationError({"space": "Inactive spaces cannot have photos changed."})
    if space.photos.count() >= MAX_PHOTOS_PER_SPACE:
        raise serializers.ValidationError(
            {"photos": f"A space can show at most {MAX_PHOTOS_PER_SPACE} photos. Remove one first."})


def presign_photo(space, *, filename, content_type):
    require_room(space)
    ext = storage.ext_for(content_type, filename)
    object_key = storage.build_object_key(space.makerspace_id, space.pk, ext)
    return object_key, storage.presigned_upload(object_key, content_type)


def cleanup_unattached(object_key):
    """Remove bytes of an upload that never became a photo (rollback / failed finalize)."""
    if not (BookableSpace.objects.filter(image_key=object_key).exists()
            or BookableSpacePhoto.objects.filter(object_key=object_key).exists()):
        storage.delete_object(object_key)
    staged = storage.staging_key(object_key)
    if staged != object_key:
        storage.delete_object(staged)


@transaction.atomic
def attach_photo(space, *, actor, object_key, size_bytes, caption=""):
    locked = _locked(space, actor)
    if not storage.is_owned_object_key(locked, object_key) or not storage.has_allowed_extension(object_key):
        raise serializers.ValidationError({"object_key": "Photo object key is outside this space."})
    if storage.public_image_key_in_use(locked.makerspace_id, object_key):
        raise serializers.ValidationError({"object_key": "This image is already in use."})
    if locked.photos.count() >= MAX_PHOTOS_PER_SPACE:
        raise serializers.ValidationError(
            {"photos": f"A space can show at most {MAX_PHOTOS_PER_SPACE} photos. Remove one first."})
    limits.add_storage(locked.makerspace, size_bytes)
    position = (locked.photos.aggregate(top=Max("position"))["top"] or 0) + 1
    photo = BookableSpacePhoto.objects.create(space=locked, object_key=object_key, size_bytes=size_bytes,
                                              caption=caption.strip(), position=position, uploaded_by=actor)
    audit.record(actor, "booking.space_photo_added", makerspace=locked.makerspace, target=locked,
                 meta={"photo_id": photo.pk, "position": position})
    return photo


@transaction.atomic
def update_photo(space, photo_id, *, actor, caption):
    locked = _locked(space, actor)
    photo = get_object_or_404(BookableSpacePhoto.objects.select_for_update(), space=locked, pk=photo_id)
    photo.caption = caption.strip()
    photo.save(update_fields=["caption"])
    audit.record(actor, "booking.space_photo_updated", makerspace=locked.makerspace, target=locked,
                 meta={"photo_id": photo.pk})
    return photo


@transaction.atomic
def reorder_photos(space, *, actor, order):
    locked = _locked(space, actor)
    rows = {row.pk: row for row in BookableSpacePhoto.objects.select_for_update().filter(space=locked)}
    if len(order) != len(set(order)) or set(order) != set(rows):
        raise serializers.ValidationError({"order": "List every photo of this space exactly once."})
    for position, pk in enumerate(order, start=1):
        if rows[pk].position != position:
            rows[pk].position = position
            rows[pk].save(update_fields=["position"])
    audit.record(actor, "booking.space_photos_reordered", makerspace=locked.makerspace, target=locked,
                 meta={"order": list(order)})
    return list(locked.photos.all())


@transaction.atomic
def delete_photo(space, photo_id, *, actor):
    locked = _locked(space, actor)
    photo = get_object_or_404(BookableSpacePhoto.objects.select_for_update(), space=locked, pk=photo_id)
    key = photo.object_key
    photo.delete()
    audit.record(actor, "booking.space_photo_removed", makerspace=locked.makerspace, target=locked,
                 meta={"photo_id": photo_id})
    storage.release_public_image_on_commit(locked.makerspace, key)


def public_photos(space):
    return [{"id": row.pk, "url": storage.public_url(row.object_key), "caption": row.caption}
            for row in space.photos.all()]

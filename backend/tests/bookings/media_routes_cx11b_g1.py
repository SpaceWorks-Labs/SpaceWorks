"""Cover and gallery operations: real rows and quota, storage edge only doubled."""
from apps.bookings import storage
from apps.bookings.models import BookableSpace
from apps.bookings.models_gallery import BookableSpacePhoto
from tests.bookings.route_support_cx11b_g1 import Route, equals, fields

ROUTES = (
    Route("admin-bookable-space-image-presign", "POST", status=201),
    Route("admin-bookable-space-image-finalize", "POST", audit=("booking.space_image_updated",)),
    Route("admin-bookable-space-image-delete", "DELETE", status=204, audit=("booking.space_image_removed",)),
    Route("admin-bookable-space-photos"),
    Route("admin-bookable-space-photos", "POST", status=201, audit=("booking.space_photo_added",)),
    Route("admin-bookable-space-photo-presign", "POST", status=201),
    Route("admin-bookable-space-photo-order", "PUT", audit=("booking.space_photos_reordered",)),
    Route("admin-bookable-space-photo", "PATCH", audit=("booking.space_photo_updated",)),
    Route("admin-bookable-space-photo", "DELETE", status=204, audit=("booking.space_photo_removed",)),
)


def setup(w, monkeypatch):
    prefix = storage.owned_prefix(w.room)
    old_key, new_key = prefix + "old.png", prefix + "new.png"
    second_key = prefix + "second.png"
    w.io = []
    def presign(key, content_type):
        w.io.append((key, content_type))
        return {"url": "https://upload.example.test/", "fields": {"key": storage.staging_key(key)}}
    monkeypatch.setattr(storage, "presigned_upload", presign)
    monkeypatch.setattr(storage, "finalize_upload", lambda key: storage.FinalizeResult("ok", 25))
    monkeypatch.setattr(storage, "sniff_is_valid_image", lambda key: True)
    monkeypatch.setattr(storage, "object_size", lambda key: 10)
    monkeypatch.setattr(storage, "delete_object", lambda key: True)
    from apps.makerspaces import limits
    monkeypatch.setattr(limits, "is_self_host", lambda: False)
    w.tenant.resource_limit_overrides = {**w.tenant.resource_limit_overrides, "storage": 100_000_000}
    w.tenant.save(update_fields=["resource_limit_overrides"])
    name, method = w.route.name, w.route.method
    if name in {"admin-bookable-space-image-presign", "admin-bookable-space-photo-presign"}:
        w.body = {"filename": "new.png", "content_type": "image/png"}
        def uploaded(r):
            key = r.data["object_key"]
            assert key.startswith(prefix) and key.endswith(".png")
            equals(w.io[-1], (key, "image/png"))
            equals(r.data["upload"]["fields"]["key"], storage.staging_key(key))
            assert storage.staging_key(key) != key
            equals(BookableSpacePhoto.objects.filter(space=w.room).count(), 0)
        w.check = uploaded
    elif name == "admin-bookable-space-image-finalize":
        w.body = {"object_key": new_key}
        def attached(r):
            fields(w.room, image_key=new_key)
            w.tenant.refresh_from_db()
            equals(w.tenant.storage_bytes_used, 25)
        w.check = attached
    elif name == "admin-bookable-space-image-delete":
        BookableSpace.objects.filter(pk=w.room.pk).update(image_key=old_key)
        w.check = lambda r: fields(w.room, image_key=None)
    else:
        photo = BookableSpacePhoto.objects.create(space=w.room, object_key=old_key,
            caption="Retained gallery image", position=1, size_bytes=10, uploaded_by=w.actor)
        if name == "admin-bookable-space-photos" and method == "GET":
            w.check = lambda r: equals([(x["id"], x["caption"], x["position"]) for x in r.data["results"]],
                [(photo.pk, "Retained gallery image", 1)])
        elif name == "admin-bookable-space-photos":
            w.body = {"object_key": new_key, "caption": "G1 new image Δ"}
            def attached(r):
                equals(BookableSpacePhoto.objects.filter(space=w.room).count(), 2)
                fields(BookableSpacePhoto.objects.get(pk=r.data["id"]), object_key=new_key,
                    caption=w.body["caption"], position=2, size_bytes=25)
            w.check = attached
        elif name == "admin-bookable-space-photo-order":
            second = BookableSpacePhoto.objects.create(space=w.room, object_key=second_key,
                caption="Second gallery image", position=2, size_bytes=10, uploaded_by=w.actor)
            w.body = {"order": [second.pk, photo.pk]}
            def ordered(r):
                equals(list(BookableSpacePhoto.objects.filter(space=w.room).order_by("position").values_list("pk", "position")),
                    [(second.pk, 1), (photo.pk, 2)])
                equals([x["id"] for x in r.data["results"]], w.body["order"])
            w.check = ordered
        else:
            w.kwargs["photo_id"] = photo.pk
            if method == "PATCH":
                w.body = {"caption": "Changed gallery caption Δ"}
                w.check = lambda r: fields(photo, caption=w.body["caption"], object_key=old_key)
            else:
                w.check = lambda r: equals(BookableSpacePhoto.objects.filter(pk=photo.pk).count(), 0)

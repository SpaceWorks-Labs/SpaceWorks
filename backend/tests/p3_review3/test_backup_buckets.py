import pytest

from apps.backup.archive_objects import capture_objects, collect_model_objects
from apps.bookings.models import BookableSpace
from apps.bookings.models_gallery import BookableSpacePhoto
from apps.bookings.models_website import BookingResourcePage, BookingResourcePageAsset
from apps.events.models import Event, EventSeries
from apps.events.models_website import EventPage, EventPageAsset
from tests.p2_events.helpers import event

pytestmark = pytest.mark.django_db


def test_gallery_covers_and_profiles_capture_from_public_bucket_but_websites_stay_private(
    lane, settings, monkeypatch, tmp_path,
):
    settings.PUBLIC_IMAGE_BUCKET = "public-images"
    settings.AWS_STORAGE_BUCKET_NAME = "private-documents"
    resource = BookableSpace.objects.create(makerspace=lane.space, name="Venue", image_key="spaces/cover.webp")
    photo = BookableSpacePhoto.objects.create(space=resource, object_key="spaces/gallery.webp", size_bytes=5)
    row = event(lane.space, image_key="events/cover.webp")
    series = EventSeries.objects.create(makerspace=lane.space, title="Series", image_key="events/series.webp",
        recurrence_timezone="UTC", dtstart_local_date=row.starts_at.date(),
        dtstart_local_time=row.starts_at.time().replace(tzinfo=None), recurrence_rule="FREQ=DAILY;COUNT=2",
        duration_minutes=120)
    page = EventPage.objects.create(makerspace=lane.space, event=row)
    event_asset = EventPageAsset.objects.create(page=page, object_key="events/website/venue.webp",
                                               size_bytes=5, alt_text="Venue")
    booking_page = BookingResourcePage.objects.create(space=resource)
    booking_asset = BookingResourcePageAsset.objects.create(page=booking_page,
        object_key="bookings/website/venue.webp", size_bytes=5, alt_text="Venue")
    lane.profile.avatar_key = "members/avatar.webp"
    lane.profile.save(update_fields=["avatar_key"])
    lane.project.image_key = "members/project.webp"
    lane.project.save(update_fields=["image_key"])
    rows = [resource, photo, row, series, event_asset, booking_asset, lane.profile, lane.project]
    objects = {"private": {}, "public_image": {}}
    for obj in rows:
        collect_model_objects(type(obj).objects.filter(pk=obj.pk), type(obj), objects,
                              fixed_makerspace_id=lane.space.pk)
    # Decision 305: account-level profile images (AccountProfile/AccountProject) are COORDINATION_ONLY,
    # never archive content, so a space capture does not collect them.
    public = {resource.image_key, photo.object_key, row.image_key, series.image_key}
    private = {event_asset.object_key, booking_asset.object_key}
    assert set(objects["public_image"]) == public
    assert set(objects["private"]) == private
    assert lane.profile.avatar_key not in objects["public_image"]
    assert lane.project.image_key not in objects["public_image"]
    assert all(item["makerspace_id"] == lane.space.pk for group in objects.values() for item in group.values())

    # No fallback between buckets: the old collector must fail on the gallery key.
    stored = {("public-images", key): b"image" for key in public}
    stored.update({("private-documents", key): b"image" for key in private})
    seen = []

    def download(bucket, key, destination, *, versioned):
        data = stored[(bucket, key)]
        seen.append((bucket, key))
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        return {"key": key, "size": len(data)}

    monkeypatch.setattr("apps.backup.archive_objects.storage.download_object", download)
    manifest = capture_objects(tmp_path, objects, {"private": "unversioned", "public_image": "unversioned"})
    assert set(seen) == set(stored)
    assert len(manifest) == len(public | private)

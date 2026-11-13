"""Place photo gallery: authority, ordering, quota accounting, public projection, venue block."""
import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.bookings import storage
from apps.bookings.models import BookableSpacePhoto
from apps.makerspaces import limits
from tests.bookings.staff_grant_helpers import client_for, grant_fixture

pytestmark = pytest.mark.django_db


@pytest.fixture
def fake_storage(monkeypatch):
    deleted = []
    monkeypatch.setattr(limits, "is_self_host", lambda: False)
    monkeypatch.setattr(storage, "finalize_upload", lambda key: storage.FinalizeResult("ok", 40))
    monkeypatch.setattr(storage, "sniff_is_valid_image", lambda key: True)
    monkeypatch.setattr(storage, "object_size", lambda key: 40)
    monkeypatch.setattr(storage, "presigned_upload", lambda key, ctype: {"url": "https://s3.test/u", "method": "PUT",
                                                                          "headers": {"Content-Type": ctype}})
    monkeypatch.setattr(storage, "delete_object", lambda key: deleted.append(key) or True)
    return deleted


def _attach(client, space, name="a"):
    key = f"spaces/{space.makerspace_id}/{space.pk}/images/{name}.png"
    return client.post(reverse("admin-bookable-space-photos", kwargs={"pk": space.pk}), {"object_key": key}, format="json")


def test_manager_uploads_reorders_captions_and_deletes(fake_storage, django_capture_on_commit_callbacks):
    tenant, manager, _grantee, space, _grant, _member = grant_fixture("edit_details", "gal-a")
    tenant.resource_limit_overrides = {"storage": 1000}
    tenant.save(update_fields=["resource_limit_overrides"])
    client = client_for(manager)
    presign = client.post(reverse("admin-bookable-space-photo-presign", kwargs={"pk": space.pk}),
                          {"filename": "a.png", "content_type": "image/png"}, format="json")
    assert presign.status_code == 201, presign.content
    assert presign.json()["object_key"].startswith(f"spaces/{tenant.pk}/{space.pk}/images/")
    first, second = _attach(client, space, "a"), _attach(client, space, "b")
    assert first.status_code == 201 and second.status_code == 201, first.content
    tenant.refresh_from_db()
    assert tenant.storage_bytes_used == 80
    ids = [first.json()["id"], second.json()["id"]]
    order = client.put(reverse("admin-bookable-space-photo-order", kwargs={"pk": space.pk}),
                       {"order": ids[::-1]}, format="json")
    assert order.status_code == 200 and [row["id"] for row in order.json()["results"]] == ids[::-1]
    bad = client.put(reverse("admin-bookable-space-photo-order", kwargs={"pk": space.pk}), {"order": ids[:1]}, format="json")
    assert bad.status_code == 400
    caption = client.patch(reverse("admin-bookable-space-photo", kwargs={"pk": space.pk, "photo_id": ids[0]}),
                           {"caption": " Front desk "}, format="json")
    assert caption.status_code == 200 and caption.json()["caption"] == "Front desk"
    with django_capture_on_commit_callbacks(execute=True):
        removed = client.delete(reverse("admin-bookable-space-photo", kwargs={"pk": space.pk, "photo_id": ids[0]}))
    assert removed.status_code == 204
    tenant.refresh_from_db()
    assert tenant.storage_bytes_used == 40 and fake_storage[-1].endswith("/a.png")
    actions = set(AuditLog.objects.filter(makerspace=tenant).values_list("action", flat=True))
    assert {"booking.space_photo_added", "booking.space_photos_reordered", "booking.space_photo_updated",
            "booking.space_photo_removed"} <= actions


def test_foreign_key_reuse_and_limit_are_refused(fake_storage):
    tenant, manager, _grantee, space, _grant, _member = grant_fixture("edit_details", "gal-b")
    client = client_for(manager)
    foreign = client.post(reverse("admin-bookable-space-photos", kwargs={"pk": space.pk}),
                          {"object_key": f"spaces/{tenant.pk}/999999/images/x.png"}, format="json")
    assert foreign.status_code == 400
    assert _attach(client, space, "dup").status_code == 201
    assert _attach(client, space, "dup").status_code == 400
    for index in range(11):
        assert _attach(client, space, f"n{index}").status_code == 201
    full = client.post(reverse("admin-bookable-space-photo-presign", kwargs={"pk": space.pk}),
                       {"filename": "z.png", "content_type": "image/png"}, format="json")
    assert full.status_code == 400 and BookableSpacePhoto.objects.filter(space=space).count() == 12


def test_grant_without_edit_details_reads_but_cannot_write(fake_storage):
    tenant, manager, grantee, space, _grant, member = grant_fixture("check_in", "gal-c")
    listing = client_for(grantee).get(reverse("admin-bookable-space-photos", kwargs={"pk": space.pk}))
    assert listing.status_code == 200 and listing.json()["can_edit"] is False
    assert _attach(client_for(grantee), space).status_code == 403
    assert client_for(member).get(reverse("admin-bookable-space-photos", kwargs={"pk": space.pk})).status_code in (403, 404)


def test_public_projection_and_event_venue(fake_storage):
    from datetime import timedelta
    from django.utils import timezone
    from apps.events.models import Event
    tenant, manager, _grantee, space, _grant, _member = grant_fixture("edit_details", "gal-d")
    tenant.enabled_modules = sorted(set(tenant.enabled_modules) | {"events"})
    tenant.location = "12 Maker Street"
    tenant.save(update_fields=["enabled_modules", "location"])
    space.is_public, space.name = True, "Main Hall"
    space.save(update_fields=["is_public", "name"])
    _attach(client_for(manager), space, "hall")
    public = APIClient().get(reverse("public-bookable-space-list", kwargs={"makerspace_slug": tenant.slug}))
    assert public.status_code == 200
    photos = public.json()[0]["photos"]
    assert len(photos) == 1 and set(photos[0]) == {"id", "url", "caption"}
    start = timezone.now() + timedelta(days=3)
    event = Event.objects.create(makerspace=tenant, title="Bootcamp", starts_at=start, ends_at=start + timedelta(hours=2),
                                 location="main hall", is_public=True, status=Event.Status.PUBLISHED)
    venue = APIClient().get(reverse("public-event-venue", kwargs={"makerspace_slug": tenant.slug,
                                                                  "public_token": event.public_token}))
    assert venue.status_code == 200, venue.content
    body = venue.json()
    assert body["host"]["location"] == "12 Maker Street" and body["space"]["name"] == "Main Hall"
    assert len(body["photos"]) == 1
    space.is_public = False
    space.save(update_fields=["is_public"])
    hidden = APIClient().get(reverse("public-event-venue", kwargs={"makerspace_slug": tenant.slug,
                                                                   "public_token": event.public_token})).json()
    assert hidden["space"] is None and hidden["photos"] == []

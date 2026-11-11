"""Real HTTP attachment charges the immutable promoted bytes in both modes."""
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.bookings import storage
from apps.bookings.models import BookableSpacePhoto
from apps.events.models import Event, EventSeries
from apps.inventory import public_image_storage
from apps.makerspaces.models import MakerspaceMembership, MemberProject
from apps.makerspaces.profile_services import profile_for
from .conftest import png

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("raced", [False, True])
def test_gallery_stages_promotes_charges_and_refuses_replay(world, image_store, raced):
    client, space = world.client(world.staff), world.resource
    presign = client.post(reverse("admin-bookable-space-photo-presign", kwargs={"pk": space.pk}),
                          {"filename": "room.png", "content_type": "image/png"}, format="json")
    assert presign.status_code == 201, presign.data
    key = presign.data["object_key"]
    assert image_store.signed[-1]["Key"] == storage.staging_key(key)
    payload = png()
    image_store.objects[storage.staging_key(key)] = (payload, "image/png")
    if raced:
        payload = png("blue") + b"winning finalizer size"
        image_store.before_put = lambda final: image_store.objects.update({final: (payload, "image/png")})
    url = reverse("admin-bookable-space-photos", kwargs={"pk": space.pk})
    response = client.post(url, {"object_key": key}, format="json")
    assert response.status_code == 201, response.data
    photo = BookableSpacePhoto.objects.get(space=space)
    assert photo.size_bytes == len(payload)
    world.space.refresh_from_db()
    assert world.space.storage_bytes_used == len(payload)
    image_store.objects[storage.staging_key(key)] = (png("blue") + b"larger", "image/png")
    assert client.post(url, {"object_key": key}, format="json").status_code == 400
    assert storage.finalize_upload(key).size == len(payload)
    assert image_store.objects[key] == (payload, "image/png")
    world.space.refresh_from_db()
    assert world.space.storage_bytes_used == len(payload)
    assert BookableSpacePhoto.objects.filter(space=space).count() == 1


@pytest.mark.parametrize("target", ["avatar", "project", "event", "series"])
def test_shared_image_owners_charge_once_and_keep_original_on_replay(world, image_store, target):
    if target in {"event", "series"}:
        now = timezone.now() + timedelta(days=2)
        if target == "event":
            holder = Event.objects.create(makerspace=world.space, title="Workshop", starts_at=now,
                                          ends_at=now + timedelta(hours=1), created_by=world.staff)
        else:
            holder = EventSeries.objects.create(makerspace=world.space, title="Weekly", recurrence_timezone="UTC",
                dtstart_local_date=now.date(), dtstart_local_time=now.time().replace(tzinfo=None),
                recurrence_rule="FREQ=WEEKLY;COUNT=2", duration_minutes=60, created_by=world.staff)
        route = "admin-event-image" if target == "event" else "admin-event-series-image"
        url = reverse(route, kwargs={"pk": holder.pk})
        client, field = world.client(world.staff), "image_key"
        extra = {}
    else:
        membership = MakerspaceMembership.objects.get(makerspace=world.space, user=world.owner)
        profile = profile_for(membership)
        holder = profile if target == "avatar" else MemberProject.objects.create(profile=profile, title="Robot")
        url = reverse("member-profile-image", kwargs={"makerspace_id": world.space.pk})
        client, field = world.client(world.owner), "avatar_key" if target == "avatar" else "image_key"
        extra = {"project_id": holder.pk} if target == "project" else {}
    presign = client.post(url, {"filename": "picture.png", "content_type": "image/png", **extra}, format="json")
    assert presign.status_code == 201, presign.data
    key = presign.data["object_key"]
    assert image_store.signed[-1]["Key"] == public_image_storage.staging_key(key)
    payload = png()
    image_store.objects[public_image_storage.staging_key(key)] = (payload, "image/png")
    response = client.put(url, {"object_key": key, **extra}, format="json")
    assert response.status_code == 200, response.data
    holder.refresh_from_db()
    assert getattr(holder, field) == key
    image_store.objects[public_image_storage.staging_key(key)] = (b"invalid replay", "image/png")
    response = client.put(url, {"object_key": key, **extra}, format="json")
    assert response.status_code == 200, response.data
    assert image_store.objects[key] == (payload, "image/png")
    assert image_store.writes == [key]
    world.space.refresh_from_db()
    assert world.space.storage_bytes_used == len(payload)

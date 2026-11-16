"""Bookable covers and gallery photos share byte quotas across web and native callers."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.db import connection
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.bookings import storage
from apps.bookings.models import BookableSpace
from apps.bookings.models_gallery import BookableSpacePhoto
from apps.makerspaces.models import Makerspace
from tests.inventory.test_alternative_creators_cx7_p4a import race
from tests.inventory.test_creator_limit_concurrency_cx7 import callers
from tests.return_helpers import make_space

pytestmark = [pytest.mark.django_db, pytest.mark.area_bookings]
KEYS = [("upload_bytes", 400, "upload_limit"), ("storage", 400, "limit_reached"),
        ("storage_public_images_bytes", 409, "storage_public_images_bytes_quota_reached")]


def world(key, surface, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    space = make_space("p4a-booking-images")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"bookings"})
    space.resource_limit_overrides = {key: 10}
    space.save(update_fields=["enabled_modules", "resource_limit_overrides"])
    sizes = {}
    monkeypatch.setattr(storage, "finalize_upload", lambda key: SimpleNamespace(status="ok", size=sizes[key]))
    monkeypatch.setattr(storage, "sniff_is_valid_image", lambda key: True)
    monkeypatch.setattr(storage, "object_size", lambda key: sizes.get(key))
    monkeypatch.setattr(storage, "delete_object", lambda key: True)
    provider = Mock(return_value={"url": "https://upload.example.test", "fields": {}})
    monkeypatch.setattr(storage, "presigned_upload", provider)
    return space, callers(space, surface, settings, monkeypatch), sizes, provider


def command(space, kind, index):
    row = BookableSpace.objects.create(makerspace=space, name=f"Room {index}")
    route = "admin-bookable-space-image-finalize" if kind == "cover" else "admin-bookable-space-photos"
    presign = "admin-bookable-space-image-presign" if kind == "cover" else "admin-bookable-space-photo-presign"
    key = f"spaces/{space.pk}/{row.pk}/images/p4a-{index}.png"
    return row, reverse(route, args=[row.pk]), reverse(presign, args=[row.pk]), key


def snapshot(space):
    return (Makerspace.objects.get(pk=space.pk).storage_bytes_used,
            list(BookableSpace.objects.order_by("pk").values()),
            list(BookableSpacePhoto.objects.order_by("pk").values()),
            list(AuditLog.objects.filter(makerspace=space).order_by("pk").values()))


@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
@pytest.mark.parametrize("kind", ["cover", "gallery"])
@pytest.mark.parametrize("key,status,code", KEYS)
def test_bookable_image_max_next_leaves_rows_audit_and_counter_unchanged(
        kind, key, status, code, surface, settings, monkeypatch):
    space, pair, sizes, _ = world(key, surface, settings, monkeypatch)
    owners = [command(space, kind, index) for index in range(2)]
    sizes.update({owners[0][3]: 10, owners[1][3]: 11 if key == "upload_bytes" else 1})
    assert pair[0].post(owners[0][1], {"object_key": owners[0][3]}, format="json").status_code == (200 if kind == "cover" else 201)
    before = snapshot(space)
    refused = pair[0].post(owners[1][1], {"object_key": owners[1][3]}, format="json")
    assert (refused.status_code, refused.json()["code"]) == (status, code)
    assert snapshot(space) == before
    assert before[0] == 10


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
@pytest.mark.parametrize("kind", ["cover", "gallery"])
@pytest.mark.parametrize("key,status,code", KEYS[1:])
def test_bookable_image_writers_race_for_last_byte(kind, key, status, code, surface, settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    space, pair, sizes, _ = world(key, surface, settings, monkeypatch)
    owners = [command(space, kind, index) for index in range(2)]
    sizes.update({object_key: 10 for _, _, _, object_key in owners})
    success = 200 if kind == "cover" else 201
    results = race(pair, [("post", url, {"object_key": object_key}, success) for _, url, _, object_key in owners])
    assert sorted(actual for actual, _ in results) == [success, status]
    assert [body["code"] for actual, body in results if actual == status] == [code]
    assert Makerspace.objects.get(pk=space.pk).storage_bytes_used == 10


@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
@pytest.mark.parametrize("kind", ["cover", "gallery"])
def test_bookable_presign_at_full_storage_has_no_provider_call(kind, surface, settings, monkeypatch):
    space, pair, _, provider = world("storage", surface, settings, monkeypatch)
    _, _, url, _ = command(space, kind, 0)
    Makerspace.objects.filter(pk=space.pk).update(storage_bytes_used=10)
    before = snapshot(space)
    refused = pair[0].post(url, {"filename": "room.png", "content_type": "image/png"}, format="json")
    assert (refused.status_code, refused.json()["code"]) == (400, "upload_limit")
    assert snapshot(space) == before
    provider.assert_not_called()

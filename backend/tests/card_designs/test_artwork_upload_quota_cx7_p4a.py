"""Artwork routes enforce upload and storage quotas before writing a final object."""
import uuid
from unittest.mock import Mock

import pytest
from django.db import connection
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.card_designs import assets, resolution
from apps.card_designs.models import CardDesignAsset
from apps.makerspaces.models import Makerspace
from tests.inventory.test_alternative_creators_cx7_p4a import race
from tests.inventory.test_creator_limit_concurrency_cx7 import callers
from tests.l3_local.helpers import card_space

pytestmark = [pytest.mark.django_db, pytest.mark.area_membership]
KEYS = [("upload_bytes", 400, "upload_limit"), ("storage", 400, "limit_reached"),
        ("storage_public_images_bytes", 409, "storage_public_images_bytes_quota_reached")]


def world(key, surface, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    space = card_space("p4a-artwork")
    space.resource_limit_overrides = {key: 10}
    space.save(update_fields=["resource_limit_overrides"])
    pair = callers(space, surface, settings, monkeypatch)
    design, _ = resolution.get_or_create(space, "member_cards")
    sizes = {}
    monkeypatch.setattr(assets, "take_staging", lambda key, cap: b"x" * sizes[key])
    monkeypatch.setattr(assets, "normalise", lambda data, **kw: (data, 1, 1, "#ffffff"))
    put = Mock()
    monkeypatch.setattr(assets, "put_bytes", put)
    presign = Mock(return_value={"url": "https://upload.example.test", "method": "PUT", "headers": {}})
    monkeypatch.setattr(assets, "presign_staging", presign)
    return space, pair, design, sizes, put, presign


def row(space, kind):
    identity = uuid.uuid4()
    return CardDesignAsset.objects.create(asset_id=identity, makerspace=space, kind=kind,
        object_key=f"card-assets/{space.pk}/{identity.hex}", content_type="image/png")


def snapshot(space):
    return (Makerspace.objects.get(pk=space.pk).storage_bytes_used,
            list(CardDesignAsset.objects.order_by("pk").values()),
            list(AuditLog.objects.filter(makerspace=space).order_by("pk").values()))


@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
@pytest.mark.parametrize("kind", ["background", "image", "watermark"])
@pytest.mark.parametrize("key,status,code", KEYS)
def test_artwork_max_next_has_no_ready_row_final_write_or_audit(kind, key, status, code, surface, settings, monkeypatch):
    space, pair, design, sizes, put, _ = world(key, surface, settings, monkeypatch)
    first, second = row(space, kind), row(space, kind)
    sizes.update({first.object_key: 10, second.object_key: 11 if key == "upload_bytes" else 1})
    url = reverse("admin-card-design-asset-finalize", args=[design.pk])
    maximum = pair[0].post(url, {"asset_id": str(first.asset_id)}, format="json")
    assert maximum.status_code == 200, maximum.content
    before = snapshot(space)
    put.reset_mock()
    refused = pair[0].post(url, {"asset_id": str(second.asset_id)}, format="json")
    assert (refused.status_code, refused.json()["code"]) == (status, code)
    assert snapshot(space) == before
    put.assert_not_called()
    assert before[0] == 10


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
@pytest.mark.parametrize("key,status,code", KEYS[1:])
def test_artwork_creators_race_for_one_last_file(key, status, code, surface, settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    space, pair, design, sizes, put, _ = world(key, surface, settings, monkeypatch)
    rows = [row(space, "image") for _ in range(2)]
    sizes.update({item.object_key: 10 for item in rows})
    url = reverse("admin-card-design-asset-finalize", args=[design.pk])
    results = race(pair, [("post", url, {"asset_id": str(item.asset_id)}, 200) for item in rows])
    assert sorted(actual for actual, _ in results) == [200, status]
    assert [body["code"] for actual, body in results if actual == status] == [code]
    assert CardDesignAsset.objects.filter(makerspace=space, ready=True).count() == 1
    assert Makerspace.objects.get(pk=space.pk).storage_bytes_used == 10
    assert put.call_count == 1


@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
def test_artwork_presign_full_storage_writes_no_pending_asset_or_presign(surface, settings, monkeypatch):
    space, pair, design, _, _, provider = world("storage", surface, settings, monkeypatch)
    Makerspace.objects.filter(pk=space.pk).update(storage_bytes_used=10)
    before = snapshot(space)
    refused = pair[0].post(reverse("admin-card-design-assets", args=[design.pk]),
                           {"kind": "image", "content_type": "image/png"}, format="json")
    assert (refused.status_code, refused.json()["code"]) == (400, "upload_limit")
    assert snapshot(space) == before
    provider.assert_not_called()


def test_artwork_cannot_hide_oversized_upload_by_reencoding_to_one_byte(settings, monkeypatch):
    space, pair, design, sizes, provider, _ = world("upload_bytes", "browser", settings, monkeypatch)
    asset = row(space, "image")
    sizes[asset.object_key] = 11
    monkeypatch.setattr(assets, "normalise", lambda *args, **kw: (b"x", 1, 1, "#ffffff"))
    before = snapshot(space)
    refused = pair[0].post(reverse("admin-card-design-asset-finalize", args=[design.pk]),
                           {"asset_id": str(asset.asset_id)}, format="json")
    assert (refused.status_code, refused.json()["code"]) == (400, "upload_limit")
    assert snapshot(space) == before
    provider.assert_not_called()

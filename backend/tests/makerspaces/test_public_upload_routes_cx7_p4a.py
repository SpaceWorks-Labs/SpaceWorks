"""Real public-image HTTP writers: external storage is the only replaced boundary."""
from types import SimpleNamespace
from unittest.mock import Mock
from datetime import time

import pytest
from django.db import connection
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.inventory import public_image_storage as images
from apps.inventory.models import InventoryProduct
from apps.events.models import Event, EventSeries
from apps.events import views_admin_image, views_series_image
from apps.machines.models import Machine, MachineType
from apps.makerspaces.account_profile import account_profile_for
from apps.makerspaces.models import Makerspace
from apps.payments.donations.models import Sponsor
from apps.shop.models import ShopProduct
from tests.inventory.test_alternative_creators_cx7_p4a import race
from tests.inventory.test_creator_limit_concurrency_cx7 import callers
from tests.return_helpers import make_space

pytestmark = [pytest.mark.django_db, pytest.mark.area_inventory, pytest.mark.area_shop,
              pytest.mark.area_payments_ledger, pytest.mark.area_membership, pytest.mark.area_machines, pytest.mark.area_events]
KINDS = ["inventory", "shop", "sponsor", "profile", "machine", "logo", "cover", "event", "series"]
KEYS = [("upload_bytes", 400, "upload_limit"), ("storage", 400, "limit_reached"),
        ("storage_public_images_bytes", 409, "storage_public_images_bytes_quota_reached")]


def setup(space, caller, kind, index):
    if kind == "inventory":
        row = InventoryProduct.objects.create(makerspace=space, name=f"Tool {index}")
        url = reverse("admin-inventory-image", args=[row.pk])
        prefix, field = "items", "image_key"
    elif kind == "shop":
        row = ShopProduct.objects.create(makerspace=space, name=f"Shop {index}", slug=f"item-{index}")
        url = reverse("admin-shop-product-image", args=[row.pk])
        prefix, field = "shop", "image_key"
    elif kind == "sponsor":
        row = Sponsor.objects.create(makerspace=space, name=f"Sponsor {index}")
        url = reverse("admin-sponsor-logo", args=[space.pk, row.pk])
        prefix, field = "sponsor", "logo_key"
    elif kind == "machine":
        machine_type = MachineType.objects.get(makerspace__isnull=True, slug="laser_cutter")
        row = Machine.objects.create(makerspace=space, machine_type=machine_type, name=f"Machine {index}")
        url = reverse("admin-machine-image", args=[row.pk])
        prefix, field = "machine", "image_key"
    elif kind in {"logo", "cover"}:
        row = space
        url = reverse(f"admin-makerspace-{kind}", args=[space.pk])
        prefix, field = "makerspace", "logo_key" if kind == "logo" else "cover_image_key"
    elif kind in {"event", "series"}:
        now = timezone.now()
        if kind == "event":
            row = Event.objects.create(makerspace=space, title=f"Event {index}", starts_at=now,
                                        ends_at=now + timezone.timedelta(days=1))
            url, prefix = reverse("admin-event-image", args=[row.pk]), "event"
        else:
            row = EventSeries.objects.create(makerspace=space, title=f"Series {index}", recurrence_timezone="UTC",
                dtstart_local_date=now.date(), dtstart_local_time=time(10), recurrence_rule="FREQ=DAILY;COUNT=1",
                duration_minutes=60)
            url, prefix = reverse("admin-event-series-image", args=[row.pk]), "event-series"
        field = "image_key"
    else:
        # Global account routes carry no tenant selection, including on a staff device grant.
        caller._credentials.pop("HTTP_X_MAKERSPACE_ID", None)
        response = caller.get(reverse("member-global-profile"))
        assert response.status_code == 200
        from apps.accounts.models import User
        actor = User.objects.get(pk=response.json()["account_id"])
        row = account_profile_for(actor)
        url = reverse("member-global-profile-image")
        prefix, field = "member", "avatar_key"
    return row, field, url, f"{prefix}/{space.pk}/p4a-{index}.png"


def world(key, surface, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    space = make_space("p4a-upload-route")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"shop", "member_accounts", "public_inventory", "machines", "events"})
    space.enabled_features = sorted(set(space.enabled_features) | {"finance.sponsors"})
    space.resource_limit_overrides = {key: 10}
    space.save(update_fields=["enabled_modules", "enabled_features", "resource_limit_overrides"])
    pair = callers(space, surface, settings, monkeypatch)
    sizes = {}
    monkeypatch.setattr(images, "finalize_upload", lambda key: SimpleNamespace(status="ok", size=sizes[key]))
    monkeypatch.setattr(images, "sniff_is_valid_image", lambda key: True)
    monkeypatch.setattr(images, "object_size", lambda key: sizes.get(key))
    monkeypatch.setattr(views_admin_image, "convert_to_webp", lambda key: key)
    monkeypatch.setattr(views_series_image, "convert_to_webp", lambda key: key)
    presign = Mock(return_value={"url": "https://upload.example.test", "fields": {}})
    monkeypatch.setattr(images, "presigned_upload", presign)
    return space, pair, sizes, presign


def snapshot(space, row):
    return (list(type(row).objects.filter(pk=row.pk).values()),
            Makerspace.objects.get(pk=space.pk).storage_bytes_used,
            list(AuditLog.objects.filter(makerspace=space).order_by("pk").values()))


@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("key,status,code", KEYS)
def test_upload_route_max_and_next_refusal_retains_owner_bytes_audit(
        surface, kind, key, status, code, settings, monkeypatch):
    space, pair, sizes, _ = world(key, surface, settings, monkeypatch)
    caller = pair[0]
    row, field, url, first = setup(space, caller, kind, 0)
    sizes[first] = 10
    maximum = caller.put(url, {"object_key": first}, format="json")
    assert maximum.status_code == 200, maximum.content
    row.refresh_from_db()
    assert getattr(row, field) == first
    second = first.replace("p4a-0", "p4a-1")
    sizes[second] = 11 if key == "upload_bytes" else 1
    before = snapshot(space, row)
    refused = caller.put(url, {"object_key": second}, format="json")
    assert (refused.status_code, refused.json()["code"]) == (status, code)
    assert snapshot(space, row) == before
    assert Makerspace.objects.get(pk=space.pk).storage_bytes_used == 10


@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
@pytest.mark.parametrize("kind", KINDS)
def test_presign_at_full_storage_never_calls_provider(kind, surface, settings, monkeypatch):
    space, pair, _, provider = world("storage", surface, settings, monkeypatch)
    row, _, url, _ = setup(space, pair[0], kind, 0)
    Makerspace.objects.filter(pk=space.pk).update(storage_bytes_used=10)
    before = snapshot(space, row)
    refused = pair[0].post(url, {"filename": "photo.png", "content_type": "image/png"}, format="json")
    assert (refused.status_code, refused.json()["code"]) == (400, "upload_limit")
    assert snapshot(space, row) == before
    provider.assert_not_called()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
@pytest.mark.parametrize("kind", ["inventory", "shop", "sponsor", "machine", "event", "series"])
@pytest.mark.parametrize("key,status,code", KEYS[1:])
def test_public_upload_writers_race_for_last_byte(kind, surface, key, status, code, settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    space, pair, sizes, _ = world(key, surface, settings, monkeypatch)
    owners = [setup(space, pair[index], kind, index) for index in range(2)]
    sizes.update({key: 10 for _, _, _, key in owners})
    results = race(pair, [("put", url, {"object_key": key}, 200) for _, _, url, key in owners])
    assert sorted(actual for actual, _ in results) == [200, status]
    assert [body["code"] for actual, body in results if actual == status] == [code]
    assert Makerspace.objects.get(pk=space.pk).storage_bytes_used == 10
    for index, (row, field, _, key) in enumerate(owners):
        row.refresh_from_db()
        assert getattr(row, field) == (key if results[index][0] == 200 else "")


@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
@pytest.mark.parametrize("kind,key,field,code", [
    ("inventory", "public_inventory", "enabled_modules", "module_disabled"),
    ("inventory", "loans.enabled", "enabled_features", "module_disabled"),
    ("machine", "machines", "enabled_modules", "module_disabled"),
    ("shop", "shop", "enabled_modules", "shop_closed"),
    ("event", "events", "enabled_modules", "module_disabled"),
    ("series", "events", "enabled_modules", "module_disabled"),
    ("sponsor", "finance.sponsors", "enabled_features", "feature_disabled")])
def test_public_upload_switch_off_retains_owner_and_on_restores(
        surface, kind, key, field, code, settings, monkeypatch):
    space, pair, sizes, provider = world("storage", surface, settings, monkeypatch)
    row, image_field, url, object_key = setup(space, pair[0], kind, 0)
    sizes[object_key] = 10
    original = list(getattr(space, field))
    assert key in original
    setattr(space, field, [value for value in original if value != key])
    space.save(update_fields=[field])
    before = snapshot(space, row)
    refused = pair[0].put(url, {"object_key": object_key}, format="json")
    assert (refused.status_code, refused.json()["code"]) == (404, code)
    assert snapshot(space, row) == before
    provider.assert_not_called()
    setattr(space, field, original)
    space.save(update_fields=[field])
    assert pair[0].put(url, {"object_key": object_key}, format="json").status_code == 200
    row.refresh_from_db()
    assert getattr(row, image_field) == object_key


@pytest.mark.parametrize("surface", ["browser", "apple", "android"])
@pytest.mark.parametrize("kind", ["event", "series"])
def test_cover_cap_checks_original_size_before_a_smaller_webp_can_hide_it(kind, surface, settings, monkeypatch):
    space, pair, sizes, _ = world("upload_bytes", surface, settings, monkeypatch)
    row, _, url, object_key = setup(space, pair[0], kind, 0)
    sizes[object_key] = 11
    def convert(key):
        result = key.replace(".png", ".webp")
        sizes[result] = 1
        return result
    converter = Mock(side_effect=convert)
    monkeypatch.setattr(views_admin_image if kind == "event" else views_series_image, "convert_to_webp", converter)
    before = snapshot(space, row)
    refused = pair[0].put(url, {"object_key": object_key}, format="json")
    assert (refused.status_code, refused.json()["code"]) == (400, "upload_limit")
    assert snapshot(space, row) == before
    converter.assert_not_called()

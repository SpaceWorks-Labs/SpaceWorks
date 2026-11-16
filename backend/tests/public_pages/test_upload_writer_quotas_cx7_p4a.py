"""Page upload writers charge class/per-file quotas before publishing private bytes."""
from types import SimpleNamespace
from unittest.mock import Mock
from conftest import _BoundedThreadPoolExecutor as ThreadPoolExecutor
from threading import Barrier

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connection, transaction, connections
from rest_framework.exceptions import APIException

from apps.audit.models import AuditLog
from apps.makerspaces import public_page_assets, website_assets
from apps.makerspaces.models import Makerspace
from apps.makerspaces.models_page_cleanup import PublicPageObjectCleanup
from apps.makerspaces.models_public_pages import MakerspacePublicPageAsset
from apps.makerspaces.public_page_services import read_editor
from tests.limits_0120.creator_races_cx7 import race_creators

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_public_site]
KEYS = [("upload_bytes", 400, "upload_limit"), ("storage", 400, "limit_reached"),
        ("storage_public_images_bytes", 409, "storage_public_images_bytes_quota_reached")]


def prepare(page_owner, key, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    space, actor = page_owner
    space.resource_limit_overrides = {key: 10}
    space.save(update_fields=["resource_limit_overrides"])
    monkeypatch.setattr(website_assets, "webp", lambda data: data)
    provider = Mock()
    monkeypatch.setattr(website_assets, "_put", provider)
    monkeypatch.setattr(website_assets, "delete_object", lambda key: True)
    return space, actor, provider


def upload(size):
    return SimpleUploadedFile("photo.png", b"x" * size, content_type="image/png")


def snapshot(space):
    return (Makerspace.objects.get(pk=space.pk).storage_bytes_used,
            list(MakerspacePublicPageAsset.objects.order_by("pk").values()),
            list(PublicPageObjectCleanup.objects.order_by("pk").values()),
            list(AuditLog.objects.filter(makerspace=space).order_by("pk").values()))


@pytest.mark.parametrize("key,status,code", KEYS)
def test_typed_page_max_next_has_no_reservation_asset_audit_or_byte_write(
        key, status, code, page_owner, settings, monkeypatch):
    space, actor, provider = prepare(page_owner, key, settings, monkeypatch)
    result = public_page_assets.upload("makerspace", space.pk, actor=actor, version=0,
                                       file=upload(10), alt_text="Workbench")
    assert result["asset"]["size_bytes"] == 10
    before = snapshot(space)
    provider.reset_mock()
    with pytest.raises(APIException) as raised:
        public_page_assets.upload("makerspace", space.pk, actor=actor, version=result["state"]["version"],
                                  file=upload(11 if key == "upload_bytes" else 1), alt_text="Second workbench")
    assert (raised.value.status_code, str(raised.value.detail["code"])) == (status, code)
    assert snapshot(space) == before
    provider.assert_not_called()
    assert before[0] == 10


@pytest.mark.parametrize("key,status,code", KEYS)
def test_legacy_page_upload_max_next_has_no_final_or_staging_write(
        key, status, code, page_owner, settings, monkeypatch):
    space, _, provider = prepare(page_owner, key, settings, monkeypatch)
    page = SimpleNamespace(makerspace=space, makerspace_id=space.pk, pk=123)
    with transaction.atomic():
        _, size = website_assets.upload(upload(10), module="bookings", page=page, copies=SimpleNamespace(created=[]))
    assert size == 10
    provider.reset_mock()
    before = snapshot(space)
    with pytest.raises(APIException) as raised, transaction.atomic():
        website_assets.upload(upload(11 if key == "upload_bytes" else 1), module="bookings", page=page,
                              copies=SimpleNamespace(created=[]))
    assert (raised.value.status_code, str(raised.value.detail["code"])) == (status, code)
    assert snapshot(space) == before
    provider.assert_not_called()


@pytest.mark.parametrize("key,status,code", KEYS[1:])
def test_legacy_page_writers_race_for_one_last_file(key, status, code, page_owner, settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    space, _, provider = prepare(page_owner, key, settings, monkeypatch)
    def create(index):
        page = SimpleNamespace(makerspace=space, makerspace_id=space.pk, pk=index + 1)
        with transaction.atomic():
            website_assets.upload(upload(10), module="bookings", page=page, copies=SimpleNamespace(created=[]))
    assert race_creators(create) == [(201, "created"), (status, code)]
    assert Makerspace.objects.get(pk=space.pk).storage_bytes_used == 10
    assert provider.call_count == 2  # one staging write and one final write


def test_typed_page_upload_switch_off_keeps_data_and_on_restores(page_owner, settings, monkeypatch):
    space, actor, provider = prepare(page_owner, "storage", settings, monkeypatch)
    # Typed pages are core; turning off the old public-site module keeps editing available.
    original = list(space.enabled_modules)
    space.enabled_modules = [key for key in original if key != "public_site"]
    space.save(update_fields=["enabled_modules"])
    state = read_editor("makerspace", space.pk, actor=actor)
    assert state["version"] == 0
    assert state["assets"] == []
    provider.assert_not_called()
    result = public_page_assets.upload("makerspace", space.pk, actor=actor, version=0,
                                       file=upload(10), alt_text="Workbench")
    assert result["asset"]["size_bytes"] == 10
    space.enabled_modules = original
    space.save(update_fields=["enabled_modules"])
    restored = read_editor("makerspace", space.pk, actor=actor)
    assert [item["id"] for item in restored["assets"]] == [result["asset"]["id"]]
    assert Makerspace.objects.get(pk=space.pk).storage_bytes_used == 10


def test_typed_page_concurrent_same_version_has_one_winner_and_no_extra_object(page_owner, settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    space, actor, provider = prepare(page_owner, "storage", settings, monkeypatch)
    barrier = Barrier(2)
    def create():
        close_old_connections()
        try:
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
            barrier.wait(timeout=15)
            try:
                public_page_assets.upload("makerspace", space.pk, actor=actor, version=0,
                                          file=upload(10), alt_text="Workbench")
            except APIException as exc:
                return exc.status_code, str(exc.detail["code"])
            return 201, "created"
        finally:
            connections.close_all()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(create) for _ in range(2)]
        assert sorted(future.result(timeout=30) for future in futures) == [(201, "created"), (409, "stale_version")]
    assert MakerspacePublicPageAsset.objects.count() == 1
    assert Makerspace.objects.get(pk=space.pk).storage_bytes_used == 10
    assert provider.call_count == 2


@pytest.mark.parametrize("kind", ["typed", "legacy"])
def test_page_upload_cap_applies_before_reencoding(kind, page_owner, settings, monkeypatch):
    space, actor, provider = prepare(page_owner, "upload_bytes", settings, monkeypatch)
    monkeypatch.setattr(website_assets, "webp", lambda data: b"x")
    before = snapshot(space)
    with pytest.raises(APIException) as raised:
        if kind == "typed":
            public_page_assets.upload("makerspace", space.pk, actor=actor, version=0,
                                      file=upload(11), alt_text="Workbench")
        else:
            page = SimpleNamespace(makerspace=space, makerspace_id=space.pk, pk=123)
            with transaction.atomic():
                website_assets.upload(upload(11), module="bookings", page=page, copies=SimpleNamespace(created=[]))
    assert (raised.value.status_code, str(raised.value.detail["code"])) == (400, "upload_limit")
    assert snapshot(space) == before
    provider.assert_not_called()

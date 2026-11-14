"""Event page upload reservations must enforce quota before creating durable object debt."""
from unittest.mock import Mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from rest_framework.exceptions import APIException

from apps.audit.models import AuditLog
from apps.events.models_website import EventPageAsset
from apps.events.services_website_assets import upload_asset
from apps.makerspaces import website_assets
from apps.makerspaces.models import Makerspace
from apps.makerspaces.models_page_cleanup import PublicPageObjectCleanup
from tests.events.collab_helpers import make_staff
from tests.events.ticketing_helpers import event_space, open_event
from tests.limits_0120.creator_races_cx7 import race_creators

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_events, pytest.mark.area_public_site]
KEYS = [("upload_bytes", 400, "upload_limit"), ("storage", 400, "limit_reached"),
        ("storage_public_images_bytes", 409, "storage_public_images_bytes_quota_reached")]


def world(key, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    space = event_space("p4a-event-upload")
    space.enabled_features = sorted(set(space.enabled_features) | {"events.website"})
    space.resource_limit_overrides = {key: 10}
    space.save(update_fields=["enabled_features", "resource_limit_overrides"])
    actor = make_staff(space)
    events = [open_event(space) for _ in range(2)]
    objects = {}
    monkeypatch.setattr(website_assets, "webp", lambda data: data)
    put = Mock(side_effect=lambda key, data, mime: objects.__setitem__(key, data))
    monkeypatch.setattr(website_assets, "_put", put)
    monkeypatch.setattr(website_assets, "object_size", lambda key: len(objects[key]) if key in objects else None)
    monkeypatch.setattr(website_assets, "delete_object", lambda key: objects.pop(key, None) is not False)
    return space, actor, events, put, objects


def upload(event, actor, size):
    return upload_asset(event, actor=actor, file=SimpleUploadedFile("image.png", b"x" * size,
                        content_type="image/png"), alt_text="Workbench")


def snapshot(space):
    return (Makerspace.objects.get(pk=space.pk).storage_bytes_used,
            list(EventPageAsset.objects.order_by("pk").values()),
            list(PublicPageObjectCleanup.objects.order_by("pk").values()),
            list(AuditLog.objects.filter(makerspace=space).order_by("pk").values()))


@pytest.mark.parametrize("key,status,code", KEYS)
def test_event_upload_max_next_writes_no_reservation_bytes_or_domain_rows(key, status, code, settings, monkeypatch):
    space, actor, events, provider, objects = world(key, settings, monkeypatch)
    asset = upload(events[0], actor, 10)
    assert asset.size_bytes == 10
    before, stored = snapshot(space), dict(objects)
    provider.reset_mock()
    with pytest.raises(APIException) as raised:
        upload(events[1], actor, 11 if key == "upload_bytes" else 1)
    assert (raised.value.status_code, str(raised.value.detail["code"])) == (status, code)
    assert snapshot(space) == before
    assert objects == stored
    provider.assert_not_called()
    assert before[0] == 10


@pytest.mark.parametrize("key,status,code", KEYS[1:])
def test_event_upload_creators_race_for_one_last_reservation(key, status, code, settings, monkeypatch):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    space, actor, events, provider, _ = world(key, settings, monkeypatch)
    assert race_creators(lambda index: upload(events[index], actor, 10)) == [(201, "created"), (status, code)]
    assert EventPageAsset.objects.count() == 1
    assert Makerspace.objects.get(pk=space.pk).storage_bytes_used == 10
    assert provider.call_count == 2


def test_event_page_cannot_hide_oversized_upload_by_compressing_it(settings, monkeypatch):
    space, actor, events, provider, objects = world("upload_bytes", settings, monkeypatch)
    monkeypatch.setattr(website_assets, "webp", lambda data: b"x")
    before = snapshot(space)
    with pytest.raises(APIException) as raised:
        upload(events[0], actor, 11)
    assert (raised.value.status_code, str(raised.value.detail["code"])) == (400, "upload_limit")
    assert snapshot(space) == before
    assert objects == {}
    provider.assert_not_called()

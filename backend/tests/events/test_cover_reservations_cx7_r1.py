"""Real PNG normalization preserves immutable covers and durable refusal debt."""
from datetime import time, timedelta
from io import BytesIO
from types import SimpleNamespace

import pytest
from botocore.exceptions import ClientError
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.audit.models import AuditLog
from apps.events.models import Event, EventSeries
from apps.inventory import public_image_storage as storage
from apps.makerspaces.models import Makerspace, StorageQuotaReservation
from apps.makerspaces.storage_reservation_cleanup import cleanup
from apps.makerspaces.storage_reservations import reserved_bytes
from tests.inventory.test_creator_limit_concurrency_cx7 import callers
from tests.return_helpers import make_space

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_events]


def png(size=(32, 24), color="red"):
    out = BytesIO()
    Image.new("RGB", size, color).save(out, format="PNG")
    return out.getvalue()


class Objects:
    def __init__(self):
        self.values, self.deletions, self.policies = {}, [], []
        self.meta = SimpleNamespace(endpoint_url="https://storage.test")

    def get_object(self, *, Bucket, Key):
        if (Bucket, Key) not in self.values:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        data, mime = self.values[Bucket, Key]
        return {"Body": BytesIO(data), "ContentType": mime, "ContentLength": len(data)}

    def head_object(self, **kwargs):
        return self.get_object(**kwargs)

    def put_object(self, *, Bucket, Key, Body, ContentType, IfNoneMatch=None):
        if IfNoneMatch == "*" and (Bucket, Key) in self.values:
            raise ClientError({"Error": {"Code": "PreconditionFailed"}}, "PutObject")
        self.values[Bucket, Key] = (Body, ContentType)
        return {}

    def generate_presigned_post(self, **kwargs):
        self.policies.append(("post", kwargs))
        return {"url": "https://storage.test/upload", "fields": {"key": kwargs["Key"]}}

    def generate_presigned_url(self, operation, *, Params, ExpiresIn):
        self.policies.append(("put", {"Params": Params, "ExpiresIn": ExpiresIn}))
        assert operation == "put_object"
        assert type(Params["ContentLength"]) is int and Params["ContentLength"] > 0
        assert Params["Key"].startswith("staging/")
        assert ExpiresIn > 0
        return "https://storage.test/upload"

    def delete(self, client, *, bucket, key, **kwargs):
        self.deletions.append((bucket, key))
        self.values.pop((bucket, key), None)
        return SimpleNamespace(absence_confirmed=True)


def world(kind, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    settings.STORAGE_CAPABILITIES_FILE = ""
    settings.STORAGE_PRESIGN_METHOD = "put"
    space = make_space("r1-cover")
    space.enabled_modules = sorted(set(space.enabled_modules or []) | {"events"})
    space.save(update_fields=["enabled_modules"])
    api = callers(space, "browser", settings, monkeypatch)[0]
    start = timezone.now() + timedelta(days=1)
    if kind == "event":
        owner = Event.objects.create(makerspace=space, title="Cover", starts_at=start, ends_at=start + timedelta(hours=1))
        route, action = "admin-event-image", "event.image_updated"
    else:
        owner = EventSeries.objects.create(makerspace=space, title="Cover", recurrence_timezone="UTC",
            dtstart_local_date=start.date(), dtstart_local_time=time(12), recurrence_rule="FREQ=WEEKLY", duration_minutes=60)
        route, action = "admin-event-series-image", "event.series_image_updated"
    objects = Objects()
    monkeypatch.setattr(storage, "_client", lambda: objects)
    monkeypatch.setattr(storage, "_public_client", lambda: objects)
    monkeypatch.setattr("apps.inventory.public_image_sniff._client", lambda: objects)
    monkeypatch.setattr("apps.evidence.storage._client", lambda: objects)
    monkeypatch.setattr("apps.object_storage.delete_all_versions", objects.delete)
    monkeypatch.setattr(storage, "delete_all_versions", objects.delete)
    url = reverse(route, kwargs={"pk": owner.pk})
    response = api.post(url, {"filename": "cover.png", "content_type": "image/png", "size": len(png())}, format="json")
    assert response.status_code == 201, response.data
    assert response.data["method"] == "PUT"
    assert response.data["headers"] == {"Content-Type": "image/png", "Content-Length": str(len(png()))}
    key = response.json()["object_key"]
    assert StorageQuotaReservation.objects.get(object_key=key).size_bytes == len(png())
    objects.values[settings.PUBLIC_IMAGE_BUCKET, storage.staging_key(key)] = (png(), "image/png")
    return space, owner, api, url, key, action, objects


@pytest.mark.parametrize("kind", ["event", "series"])
def test_original_presign_replay_cannot_replace_normalized_cover(kind, settings, monkeypatch):
    space, owner, api, url, key, action, objects = world(kind, settings, monkeypatch)
    assert api.put(url, {"object_key": key}, format="json").status_code == 200
    owner.refresh_from_db()
    accepted_key = owner.image_key
    accepted = objects.values[settings.PUBLIC_IMAGE_BUCKET, accepted_key][0]
    with Image.open(BytesIO(accepted)) as image:
        assert image.format == "WEBP"
    assert accepted_key == key.rsplit(".", 1)[0] + ".webp"
    replay_bytes = png((80, 60), "blue")
    assert len(replay_bytes) != len(png())
    objects.values[settings.PUBLIC_IMAGE_BUCKET, storage.staging_key(key)] = (replay_bytes, "image/png")
    refused = api.put(url, {"object_key": key}, format="json")
    assert (refused.status_code, refused.json()["code"]) == (400, "upload_limit")
    owner.refresh_from_db()
    space.refresh_from_db()
    assert owner.image_key == accepted_key
    assert objects.values[settings.PUBLIC_IMAGE_BUCKET, accepted_key][0] == accepted
    assert (space.storage_bytes_used, reserved_bytes(space)) == (len(accepted), 0)
    assert AuditLog.objects.filter(makerspace=space, action=action).count() == 1


@pytest.mark.parametrize("kind", ["event", "series"])
def test_quota_refusal_preserves_normalized_key_debt_until_exact_key_cleanup(kind, settings, monkeypatch):
    space, owner, api, url, key, action, objects = world(kind, settings, monkeypatch)
    receipt = StorageQuotaReservation.objects.get(object_key=key)
    Makerspace.objects.filter(pk=space.pk).update(resource_limit_overrides={"storage": 1})
    refused = api.put(url, {"object_key": key}, format="json")
    assert (refused.status_code, refused.json()["code"]) == (400, "limit_reached")
    receipt.refresh_from_db()
    assert receipt.final_key == key.rsplit(".", 1)[0] + ".webp"
    assert (settings.PUBLIC_IMAGE_BUCKET, receipt.final_key) in objects.values
    assert (receipt.converted, receipt.released, reserved_bytes(space)) == (False, False, receipt.size_bytes)
    owner.refresh_from_db()
    assert owner.image_key == ""
    assert Makerspace.objects.get(pk=space.pk).storage_bytes_used == 0
    assert AuditLog.objects.filter(makerspace=space, action=action).count() == 0
    objects.deletions.clear()
    assert cleanup(receipt.pk, now=receipt.expires_at + timedelta(seconds=1)) is True
    expected = {(receipt.bucket, receipt.staging_key), (receipt.final_bucket, key), (receipt.final_bucket, receipt.final_key)}
    assert set(objects.deletions) == expected
    assert all(pair not in objects.values for pair in expected)
    assert reserved_bytes(space) == 0
    assert AuditLog.objects.filter(makerspace=space, action="storage.upload_reservation_released").count() == 1


@pytest.mark.parametrize("kind", ["event", "series"])
@pytest.mark.parametrize("state", ["converted", "released", "cleaning"])
def test_closed_reservation_is_fenced_before_any_promotion_or_normalization(kind, state, settings, monkeypatch):
    space, owner, api, url, key, action, objects = world(kind, settings, monkeypatch)
    StorageQuotaReservation.objects.filter(object_key=key).update(**{state: True})
    before = dict(objects.values)
    refused = api.put(url, {"object_key": key}, format="json")
    assert (refused.status_code, refused.json()["code"]) == (400, "upload_limit")
    assert objects.values == before
    assert objects.deletions == []
    assert AuditLog.objects.filter(makerspace=space, action=action).count() == 0


@pytest.mark.parametrize("kind", ["event", "series"])
def test_conditional_normalization_reuses_the_winning_final_snapshot(kind, settings, monkeypatch):
    from apps.events.programme.cover import canonical_cover_webp
    space, owner, api, url, key, action, objects = world(kind, settings, monkeypatch)
    final_key = key.rsplit(".", 1)[0] + ".webp"
    winner = canonical_cover_webp(png((50, 30), "blue"))
    objects.values[settings.PUBLIC_IMAGE_BUCKET, final_key] = (winner, "image/webp")
    assert api.put(url, {"object_key": key}, format="json").status_code == 200
    owner.refresh_from_db()
    space.refresh_from_db()
    assert owner.image_key == final_key
    assert objects.values[settings.PUBLIC_IMAGE_BUCKET, final_key][0] == winner
    assert (space.storage_bytes_used, reserved_bytes(space)) == (len(winner), 0)
    assert AuditLog.objects.filter(makerspace=space, action=action).count() == 1


@pytest.mark.parametrize("kind", ["event", "series"])
def test_audit_failure_rolls_back_attachment_but_not_the_normalized_destination_claim(kind, settings, monkeypatch):
    from apps.audit import services as audit
    from django.db import IntegrityError
    space, owner, api, url, key, action, objects = world(kind, settings, monkeypatch)
    original = audit.record
    def fail(actor, name, **kwargs):
        if name == action:
            raise IntegrityError("injected attachment audit failure")
        return original(actor, name, **kwargs)
    monkeypatch.setattr(audit, "record", fail)
    with pytest.raises(IntegrityError, match="injected attachment audit failure"):
        api.put(url, {"object_key": key}, format="json")
    receipt = StorageQuotaReservation.objects.get(object_key=key)
    owner.refresh_from_db()
    assert owner.image_key == ""
    assert (receipt.final_key, receipt.converted) == (key.rsplit(".", 1)[0] + ".webp", False)
    assert (settings.PUBLIC_IMAGE_BUCKET, receipt.final_key) in objects.values
    assert reserved_bytes(space) == receipt.size_bytes
    assert Makerspace.objects.get(pk=space.pk).storage_bytes_used == 0
    assert AuditLog.objects.filter(makerspace=space, action=action).count() == 0


@pytest.mark.parametrize("kind", ["event", "series"])
def test_events_module_off_keeps_pending_upload_and_restoration_allows_attachment(kind, settings, monkeypatch):
    space, owner, api, url, key, action, objects = world(kind, settings, monkeypatch)
    original = space.enabled_modules
    Makerspace.objects.filter(pk=space.pk).update(enabled_modules=[name for name in original if name != "events"])
    before = dict(objects.values)
    refused = api.put(url, {"object_key": key}, format="json")
    assert (refused.status_code, refused.json()["code"]) == (404, "module_disabled")
    assert objects.values == before
    assert StorageQuotaReservation.objects.get(object_key=key).converted is False
    Makerspace.objects.filter(pk=space.pk).update(enabled_modules=original)
    assert api.put(url, {"object_key": key}, format="json").status_code == 200
    assert AuditLog.objects.filter(makerspace=space, action=action).count() == 1


@pytest.mark.parametrize("kind", ["event", "series"])
def test_original_upload_cannot_replace_another_owners_accepted_cover(kind, settings, monkeypatch):
    space, owner, api, url, key, action, objects = world(kind, settings, monkeypatch)
    assert api.put(url, {"object_key": key}, format="json").status_code == 200
    owner.refresh_from_db()
    if kind == "event":
        other = Event.objects.create(makerspace=space, title="Other", starts_at=owner.starts_at, ends_at=owner.ends_at)
    else:
        other = EventSeries.objects.create(makerspace=space, title="Other", recurrence_timezone="UTC",
            dtstart_local_date=owner.dtstart_local_date, dtstart_local_time=time(13),
            recurrence_rule="FREQ=WEEKLY", duration_minutes=60)
    route = "admin-event-image" if kind == "event" else "admin-event-series-image"
    objects.values[settings.PUBLIC_IMAGE_BUCKET, storage.staging_key(key)] = (png((80, 60), "blue"), "image/png")
    before = dict(objects.values)
    refused = api.put(reverse(route, kwargs={"pk": other.pk}), {"object_key": key}, format="json")
    assert (refused.status_code, refused.json()["code"]) == (400, "upload_limit")
    other.refresh_from_db()
    assert other.image_key == ""
    assert objects.values == before
    assert AuditLog.objects.filter(makerspace=space, action=action).count() == 1


@pytest.mark.parametrize("kind", ["event", "series"])
def test_unconfirmed_original_deletion_keeps_normalization_pending_and_returns_typed_503(kind, settings, monkeypatch):
    space, owner, api, url, key, action, objects = world(kind, settings, monkeypatch)
    def delete(client, *, bucket, key: str, **kwargs):
        if key.endswith(".png") and not key.startswith("staging/"):
            return SimpleNamespace(absence_confirmed=False)
        return objects.delete(client, bucket=bucket, key=key, **kwargs)
    monkeypatch.setattr("apps.object_storage.delete_all_versions", delete)
    refused = api.put(url, {"object_key": key}, format="json")
    assert (refused.status_code, refused.json()["code"]) == (503, "storage_unavailable")
    receipt = StorageQuotaReservation.objects.get(object_key=key)
    assert receipt.converted is False
    assert reserved_bytes(space) == receipt.size_bytes
    assert (settings.PUBLIC_IMAGE_BUCKET, receipt.final_key) in objects.values
    assert (settings.PUBLIC_IMAGE_BUCKET, receipt.object_key) in objects.values
    owner.refresh_from_db()
    assert owner.image_key == ""
    assert AuditLog.objects.filter(makerspace=space, action=action).count() == 0


@pytest.mark.parametrize("kind", ["event", "series"])
def test_put_only_cover_requires_size_without_new_authorization_or_debt(kind, settings, monkeypatch):
    space, owner, api, url, key, action, objects = world(kind, settings, monkeypatch)
    before = (list(StorageQuotaReservation.objects.order_by("pk").values()),
              list(AuditLog.objects.order_by("pk").values()), list(objects.policies))
    refused = api.post(url, {"filename": "cover.png", "content_type": "image/png"}, format="json")
    assert (refused.status_code, refused.data["code"]) == (400, "upload_size_required")
    assert (list(StorageQuotaReservation.objects.order_by("pk").values()),
            list(AuditLog.objects.order_by("pk").values()), objects.policies) == before
    owner.refresh_from_db()
    assert owner.image_key == ""

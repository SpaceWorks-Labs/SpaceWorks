"""Kiosk replay keeps each storage authorization inside its accounted byte debt."""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.evidence import storage
from apps.evidence.models import EvidencePhoto
from apps.hardware_requests.models import ReplayCommand
from apps.makerspaces.models import Makerspace, StorageQuotaReservation
from apps.storage_capabilities import presigning
from tests.cloud.storage.test_contracts import contract
from tests.hardware_requests.replay_helpers import envelope, prepare, replay_env

pytestmark = [pytest.mark.django_db, pytest.mark.area_lending, pytest.mark.area_inventory]


@pytest.fixture
def upload_env(replay_env, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    settings.SPACEWORKS_DEPLOYMENT_MODE = "host"
    settings.STORAGE_PRESIGN_METHOD = "auto"
    settings.EVIDENCE_MAX_BYTES = 10
    settings.EVIDENCE_URL_TTL_SECONDS = 300
    clock = SimpleNamespace(now=timezone.now())
    monkeypatch.setattr(timezone, "now", lambda: clock.now)
    provider = Mock(meta=SimpleNamespace(endpoint_url="https://storage.test"))
    provider.generate_presigned_post.return_value = {"url": "https://storage.test/post", "fields": {}}
    provider.generate_presigned_url.return_value = "https://storage.test/put"
    monkeypatch.setattr(storage, "_client", lambda: provider)
    monkeypatch.setattr(storage, "_public_client", lambda: provider)
    monkeypatch.setattr("apps.evidence.services_upload.presigned_upload", storage.presigned_upload)
    monkeypatch.setattr("apps.hardware_requests.replay_prepare.presigned_upload", storage.presigned_upload)

    def transport(method):
        value = contract(max_object_bytes=10, presign_methods=frozenset({method}))
        monkeypatch.setattr(presigning, "capabilities_for", lambda *a, **kw: value)
        monkeypatch.setattr(presigning, "verified_state", lambda *a: SimpleNamespace(facts={"presign_methods": [method]}))
    transport("post")
    return replay_env, provider, clock, transport


def command(env, **sizes):
    return envelope(env, "reviewed_issue", {"request_id": env.request.pk},
                    evidence={"evidence_type": "issue", "content_type": "image/jpeg", **sizes})


def audit_counts():
    return tuple(AuditLog.objects.filter(action=action).count() for action in (
        "kiosk.evidence_upload_issued", "kiosk.replay_prepared"))


def state():
    return (list(ReplayCommand.objects.values()), list(EvidencePhoto.objects.values()),
            list(StorageQuotaReservation.objects.values()), list(AuditLog.objects.order_by("pk").values()))


def assert_post(provider, row, settings, *, count):
    assert provider.generate_presigned_post.call_count == count
    for call in provider.generate_presigned_post.call_args_list:
        assert call.kwargs == {
            "Bucket": settings.AWS_STORAGE_BUCKET_NAME, "Key": row.staging_key,
            "Fields": {"Content-Type": "image/jpeg"},
            "Conditions": [{"Content-Type": "image/jpeg"}, ["content-length-range", 1, 4]],
            "ExpiresIn": 300,
        }
    provider.generate_presigned_url.assert_not_called()


def test_omitted_size_retry_keeps_the_original_reduced_capacity_policy(upload_env, settings):
    env, provider, clock, _ = upload_env
    env.space.resource_limit_overrides = {"storage": 4}
    env.space.save(update_fields=["resource_limit_overrides"])
    data = command(env)
    first = prepare(env, data)
    assert first.status_code == 200, first.data
    before = state()
    again = prepare(env, data)
    assert again.status_code == 200, again.data
    assert again.data == first.data
    assert state() == before
    row = StorageQuotaReservation.objects.get()
    assert (row.size_bytes, row.converted, row.cleaning, row.released, row.expires_at) == (
        4, False, False, False, clock.now + timedelta(seconds=300))
    assert_post(provider, row, settings, count=2)
    assert audit_counts() == (1, 1)
    assert Makerspace.objects.get(pk=env.space.pk).storage_bytes_used == 0


def test_retry_before_expiry_atomically_retains_debt_for_the_new_full_ttl(upload_env, settings):
    env, provider, clock, _ = upload_env
    env.space.resource_limit_overrides = {"storage": 4}
    env.space.save(update_fields=["resource_limit_overrides"])
    data = command(env)
    first = prepare(env, data)
    assert first.status_code == 200, first.data
    original = StorageQuotaReservation.objects.get()
    photos = list(EvidencePhoto.objects.values())
    commands = list(ReplayCommand.objects.values())
    clock.now = original.expires_at - timedelta(seconds=1)
    again = prepare(env, data)
    assert again.status_code == 200, again.data
    assert again.data == first.data
    row = StorageQuotaReservation.objects.get()
    assert (row.pk, row.size_bytes, row.converted, row.cleaning, row.released, row.expires_at) == (
        original.pk, 4, False, False, False, clock.now + timedelta(seconds=300))
    assert list(EvidencePhoto.objects.values()) == photos
    assert list(ReplayCommand.objects.values()) == commands
    assert audit_counts() == (1, 1)
    assert_post(provider, row, settings, count=2)


@pytest.mark.parametrize("closed", ["expiry", "released", "cleaning", "converted"])
def test_closed_or_exactly_expired_receipt_never_issues_another_authorization(upload_env, closed):
    env, provider, clock, _ = upload_env
    data = command(env)
    assert prepare(env, data).status_code == 200
    row = StorageQuotaReservation.objects.get()
    if closed == "expiry":
        clock.now = row.expires_at
    else:
        StorageQuotaReservation.objects.filter(pk=row.pk).update(**{closed: True})
    before = state()
    provider.reset_mock()
    response = prepare(env, data)
    assert (response.status_code, response.data["code"]) == (400, "evidence_invalid")
    assert state() == before
    provider.generate_presigned_post.assert_not_called()
    provider.generate_presigned_url.assert_not_called()
    assert audit_counts() == (1, 1)


@pytest.mark.parametrize("sizes", [{"size": 4}, {"size_bytes": 4}, {"size": 4, "size_bytes": 3}])
def test_put_only_first_prepare_and_retry_reuse_the_authoritative_declaration(upload_env, sizes, settings):
    env, provider, clock, transport = upload_env
    transport("put")
    data = command(env, **sizes)
    first, again = prepare(env, data), prepare(env, data)
    assert first.status_code == again.status_code == 200, (first.data, again.data)
    assert first.data == again.data
    assert first.data["upload"]["headers"] == {"Content-Type": "image/jpeg", "Content-Length": "4"}
    row = StorageQuotaReservation.objects.get()
    assert (row.size_bytes, row.expires_at, row.converted, row.released) == (
        4, clock.now + timedelta(seconds=300), False, False)
    assert EvidencePhoto.objects.get().size_bytes == 4
    assert ReplayCommand.objects.count() == EvidencePhoto.objects.count() == 1
    assert audit_counts() == (1, 1)
    assert provider.generate_presigned_url.call_count == 2
    for call in provider.generate_presigned_url.call_args_list:
        assert call.args == ("put_object",)
        assert call.kwargs == {"Params": {
            "Bucket": settings.AWS_STORAGE_BUCKET_NAME, "Key": row.staging_key,
            "ContentType": "image/jpeg", "ContentLength": 4,
        }, "ExpiresIn": 300}
    provider.generate_presigned_post.assert_not_called()


@pytest.mark.parametrize("sizes,code", [({}, "upload_size_required"), ({"size": 11}, "upload_limit")])
def test_put_only_refusal_preserves_the_specific_http_error_and_rolls_back(upload_env, sizes, code):
    env, provider, _, transport = upload_env
    transport("put")
    before = state()
    response = prepare(env, command(env, **sizes))
    assert (response.status_code, response.data["code"]) == (400, code)
    assert response["Cache-Control"] == "private, no-store"
    assert state() == before
    assert audit_counts() == (0, 0)
    provider.generate_presigned_post.assert_not_called()
    provider.generate_presigned_url.assert_not_called()


@pytest.mark.parametrize("capacity,status,code", [(4, 200, None), (3, 400, "limit_reached")])
def test_pre_reservation_command_requires_fresh_admission_without_replacing_its_photo(upload_env, capacity, status, code):
    env, provider, _, transport = upload_env
    transport("put")
    data = command(env, size=4)
    first = prepare(env, data)
    assert first.status_code == 200, first.data
    StorageQuotaReservation.objects.all().delete()  # Emulate a retained pre-reservation command.
    env.space.resource_limit_overrides = {"storage": capacity}
    env.space.save(update_fields=["resource_limit_overrides"])
    before = state()
    provider.reset_mock()
    response = prepare(env, data)
    assert response.status_code == status, response.data
    if code:
        assert response.data["code"] == code
        assert state() == before
        provider.generate_presigned_url.assert_not_called()
    else:
        assert response.data == first.data
        assert StorageQuotaReservation.objects.get().size_bytes == 4
        assert provider.generate_presigned_url.call_count == 1
        assert list(ReplayCommand.objects.values()) == before[0]
        assert list(EvidencePhoto.objects.values()) == before[1]
    assert audit_counts() == (1, 1)


def test_slow_retry_signing_keeps_debt_until_a_full_ttl_after_the_authorization(upload_env):
    env, provider, clock, _ = upload_env
    data = command(env)
    assert prepare(env, data).status_code == 200
    row = StorageQuotaReservation.objects.get()
    clock.now = row.expires_at - timedelta(seconds=1)

    def sign(**kwargs):
        clock.now += timedelta(seconds=7)
        return {"url": "https://storage.test/renewed", "fields": {}}
    provider.generate_presigned_post.side_effect = sign
    response = prepare(env, data)
    assert response.status_code == 200, response.data
    row.refresh_from_db()
    assert (row.size_bytes, row.expires_at, row.converted, row.released) == (
        10, clock.now + timedelta(seconds=300), False, False)
    assert provider.generate_presigned_post.call_args.kwargs["ExpiresIn"] == 300
    assert audit_counts() == (1, 1)


def test_failed_retry_signing_preserves_the_original_receipt_and_audits(upload_env):
    from botocore.exceptions import ClientError
    env, provider, clock, _ = upload_env
    data = command(env)
    assert prepare(env, data).status_code == 200
    row = StorageQuotaReservation.objects.get()
    clock.now = row.expires_at - timedelta(seconds=1)
    before = state()
    provider.generate_presigned_post.side_effect = ClientError({"Error": {"Code": "AccessDenied"}}, "presign")
    response = prepare(env, data)
    assert (response.status_code, response.data["code"]) == (503, "storage_unavailable")
    assert state() == before
    assert audit_counts() == (1, 1)


@pytest.mark.parametrize("field,key,code", [
    ("enabled_modules", "evidence_uploads", "module_disabled"),
    ("enabled_modules", "request_workflow", "module_disabled"),
    ("enabled_features", "inventory.kiosk", "feature_disabled"),
])
def test_retry_rechecks_connected_modules_and_kiosk_switch_then_restores_same_upload(upload_env, field, key, code):
    env, provider, _, _ = upload_env
    data = command(env)
    first = prepare(env, data)
    assert first.status_code == 200, first.data
    retained = state()
    original = list(getattr(env.space, field))
    assert key in original
    setattr(env.space, field, [value for value in original if value != key])
    env.space.save(update_fields=[field])
    provider.reset_mock()
    refused = prepare(env, data)
    assert (refused.status_code, refused.data["code"]) == (404, code)
    assert state() == retained
    provider.generate_presigned_post.assert_not_called()
    provider.generate_presigned_url.assert_not_called()
    setattr(env.space, field, original)
    env.space.save(update_fields=[field])
    restored = prepare(env, data)
    assert restored.status_code == 200, restored.data
    assert restored.data == first.data
    assert state() == retained
    assert provider.generate_presigned_post.call_count == 1
    assert audit_counts() == (1, 1)

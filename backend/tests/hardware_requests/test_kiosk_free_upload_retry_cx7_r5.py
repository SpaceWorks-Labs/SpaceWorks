"""Real free deployment admission participates in kiosk evidence retries."""
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.evidence import storage
from apps.evidence.models import EvidencePhoto
from apps.hardware_requests.models import ReplayCommand
from apps.makerspaces.models import StorageQuotaReservation
from apps.operations.models import CloudObjectAccount, CloudObjectReservation, StorageCapabilityState
from apps.operations.cloud_quotas.storage import object_digest
from apps.storage_capabilities import runtime
from apps.storage_capabilities.contracts import CapabilityError, StorageIdentity
from tests.cloud.storage.test_contracts import contract
from tests.hardware_requests.replay_helpers import envelope, prepare, replay_env

pytestmark = [pytest.mark.django_db, pytest.mark.area_lending, pytest.mark.area_inventory]


@pytest.fixture
def free_upload(replay_env, settings, monkeypatch):
    settings.MANAGED_PLANS_ENABLED = False
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "free"
    settings.SPACEWORKS_DEPLOYMENT_MODE = "host"
    settings.STORAGE_PRESIGN_METHOD = "auto"
    settings.EVIDENCE_MAX_BYTES = 10
    settings.EVIDENCE_URL_TTL_SECONDS = 300
    settings.FREE_OBJECT_CAP_BYTES = 10
    settings.AWS_S3_ENDPOINT_URL = "https://storage.test"
    clock = SimpleNamespace(now=timezone.now())
    monkeypatch.setattr(timezone, "now", lambda: clock.now)
    provider = Mock(meta=SimpleNamespace(endpoint_url="https://storage.test", region_name="auto"))
    provider.generate_presigned_url.return_value = "https://storage.test/conditional-put"
    identity = StorageIdentity.build("https://storage.test", "auto", settings.AWS_STORAGE_BUCKET_NAME)
    value = replace(contract(), identity=identity, max_object_bytes=10)
    monkeypatch.setattr(runtime, "configured_contracts", lambda: {"private": value})
    monkeypatch.setattr(storage, "configured_contracts", lambda: {"private": value})
    # Exercise actual capability verification against a persisted supported proof.
    StorageCapabilityState.objects.create(identity_fingerprint=identity.fingerprint,
        identity={"endpoint": identity.endpoint, "region": identity.region, "bucket": identity.bucket},
        logical_role="private", generation=value.generation, configuration_fingerprint=value.fingerprint,
        verified_at=clock.now, facts={"presign_methods": ["put"], "conditional_create": True,
                                      "put_conditional_presign": True})
    CloudObjectAccount.objects.create(identity=identity.fingerprint, used=6, sampled_at=clock.now, reason="")
    monkeypatch.setattr(storage, "_client", lambda: provider)
    monkeypatch.setattr(storage, "_public_client", lambda: provider)
    monkeypatch.setattr("apps.evidence.services_upload.presigned_upload", storage.presigned_upload)
    monkeypatch.setattr("apps.hardware_requests.replay_prepare.presigned_upload", storage.presigned_upload)
    replay_env.space.resource_limit_overrides = {"storage": 4, "storage_evidence_bytes": 4}
    replay_env.space.save(update_fields=["resource_limit_overrides"])
    data = envelope(replay_env, "reviewed_issue", {"request_id": replay_env.request.pk},
        evidence={"evidence_type": "issue", "content_type": "image/jpeg", "size": 4})
    return replay_env, data, provider, clock, identity


def snapshot():
    return [list(model.objects.order_by("pk").values()) for model in (
        ReplayCommand, EvidencePhoto, StorageQuotaReservation, CloudObjectReservation, CloudObjectAccount, AuditLog)]


def assert_debt(env, identity, clock):
    tenant = StorageQuotaReservation.objects.get(makerspace=env.space)
    cloud = CloudObjectReservation.objects.get()
    photo = EvidencePhoto.objects.get(makerspace=env.space)
    assert (tenant.object_key, tenant.staging_key, tenant.size_bytes, tenant.expires_at,
            tenant.converted, tenant.cleaning, tenant.released) == (
        photo.object_key, "staging/" + photo.object_key, 4, clock.now + timedelta(seconds=300), False, False, False)
    assert (cloud.pk, cloud.account_id, cloud.bytes, cloud.expires_at, cloud.server_owned, cloud.state) == (
        object_digest(identity.fingerprint, tenant.staging_key), identity.fingerprint, 4,
        tenant.expires_at, False, "reserved")
    assert CloudObjectReservation.objects.count() == StorageQuotaReservation.objects.filter(makerspace=env.space).count() == 1
    assert CloudObjectAccount.objects.get(pk=identity.fingerprint).used == 6
    return tenant


def test_free_initial_and_identical_retry_keep_one_conditional_authorization_debt(free_upload, settings):
    env, data, provider, clock, identity = free_upload
    first = prepare(env, data)
    assert first.status_code == 200, first.data
    tenant = assert_debt(env, identity, clock)
    stable = snapshot()
    again = prepare(env, data)
    assert again.status_code == 200, again.data
    assert again.data == first.data
    assert snapshot() == stable
    assert_debt(env, identity, clock)
    assert first.data["upload"]["headers"] == {
        "Content-Type": "image/jpeg", "Content-Length": "4", "If-None-Match": "*"}
    assert first.data["upload"]["method"] == "PUT"
    assert provider.generate_presigned_url.call_count == 2
    for call in provider.generate_presigned_url.call_args_list:
        assert call.args == ("put_object",)
        assert call.kwargs == {"Params": {"Bucket": settings.AWS_STORAGE_BUCKET_NAME,
            "Key": tenant.staging_key, "ContentType": "image/jpeg", "ContentLength": 4,
            "IfNoneMatch": "*"}, "ExpiresIn": 300}
    provider.generate_presigned_post.assert_not_called()
    assert ReplayCommand.objects.get(makerspace=env.space).evidence_id == EvidencePhoto.objects.get(makerspace=env.space).pk
    assert [AuditLog.objects.filter(makerspace=env.space, action=action).count() for action in (
        "kiosk.evidence_upload_issued", "kiosk.replay_prepared")] == [1, 1]


@pytest.mark.parametrize("initial", [True, False])
def test_slow_free_signing_retains_both_layers_for_a_whole_ttl_after_signing(free_upload, initial):
    env, data, provider, clock, identity = free_upload
    if not initial:
        assert prepare(env, data).status_code == 200
        clock.now += timedelta(seconds=299)
    def sign(*args, **kwargs):
        clock.now += timedelta(seconds=7)
        return "https://storage.test/conditional-put"
    provider.generate_presigned_url.side_effect = sign
    response = prepare(env, data)
    assert response.status_code == 200, response.data
    assert_debt(env, identity, clock)


def test_failed_first_free_signature_rolls_back_command_photo_and_both_reservations(free_upload):
    env, data, provider, _, _ = free_upload
    before = snapshot()
    provider.generate_presigned_url.side_effect = ClientError({"Error": {"Code": "AccessDenied"}}, "presign")
    response = prepare(env, data)
    assert (response.status_code, response.data["code"]) == (503, "storage_unavailable")
    assert snapshot() == before


@pytest.mark.parametrize("layer,state", [
    ("tenant", "expiry"), ("tenant", "released"), ("tenant", "cleaning"), ("tenant", "converted"),
    ("cloud", "expiry"), ("cloud", "writing"), ("cloud", "uncertain"), ("cloud", "finalized"),
    ("cloud", "reconciled"),
])
def test_free_retry_refuses_expired_or_closed_debt_without_signing(free_upload, layer, state):
    env, data, provider, clock, _ = free_upload
    assert prepare(env, data).status_code == 200
    if layer == "tenant":
        changes = {"expires_at": clock.now} if state == "expiry" else {state: True}
        StorageQuotaReservation.objects.filter(makerspace=env.space).update(**changes)
    else:
        changes = {"expires_at": clock.now} if state == "expiry" else {"state": state}
        CloudObjectReservation.objects.update(**changes)
    before = snapshot()
    provider.reset_mock()
    response = prepare(env, data)
    expected = (400, "evidence_invalid") if layer == "tenant" else (503, "storage_unavailable")
    assert (response.status_code, response.data["code"]) == expected
    assert snapshot() == before
    provider.generate_presigned_url.assert_not_called()
    provider.generate_presigned_post.assert_not_called()


@pytest.mark.parametrize("failure", ["provider", "retention", "cap", "sample", "conditional_proof"])
def test_free_failed_renewal_preserves_both_debts_and_original_audits(free_upload, failure, settings, monkeypatch):
    from apps.operations.cloud_quotas import storage as accounting
    env, data, provider, clock, _ = free_upload
    assert prepare(env, data).status_code == 200
    clock.now += timedelta(seconds=299)
    if failure == "provider":
        def fail(*args, **kwargs):
            clock.now += timedelta(seconds=7)
            raise ClientError({"Error": {"Code": "AccessDenied"}}, "presign")
        provider.generate_presigned_url.side_effect = fail
    elif failure == "retention":
        original = accounting.cover_upload_authorization
        def fail(*args, **kwargs):
            original(*args, **kwargs)
            raise CapabilityError("storage_reservation_reconciliation_required")
        monkeypatch.setattr(accounting, "cover_upload_authorization", fail)
    elif failure == "cap":
        settings.FREE_OBJECT_CAP_BYTES = 9
    elif failure == "sample":
        CloudObjectAccount.objects.exclude(pk="deployment").update(reason="storage_usage_unverified")
    else:
        proof = StorageCapabilityState.objects.get()
        proof.facts["put_conditional_presign"] = False
        proof.save(update_fields=["facts"])
    before = snapshot()
    provider.reset_mock()
    response = prepare(env, data)
    assert (response.status_code, response.data["code"]) == (503, "storage_unavailable")
    assert snapshot() == before
    assert provider.generate_presigned_url.call_count == (1 if failure in {"provider", "retention"} else 0)


@pytest.mark.parametrize("field,key,code", [
    ("enabled_modules", "evidence_uploads", "module_disabled"),
    ("enabled_modules", "request_workflow", "module_disabled"),
    ("enabled_features", "inventory.kiosk", "feature_disabled"),
])
def test_free_retry_switch_off_preserves_debts_and_on_restores_same_upload(free_upload, field, key, code):
    env, data, provider, _, _ = free_upload
    first = prepare(env, data)
    assert first.status_code == 200
    before = snapshot()
    saved = getattr(env.space, field)
    setattr(env.space, field, [value for value in saved if value != key])
    env.space.save(update_fields=[field])
    provider.reset_mock()
    refused = prepare(env, data)
    assert (refused.status_code, refused.data["code"]) == (404, code)
    assert snapshot() == before
    provider.generate_presigned_url.assert_not_called()
    setattr(env.space, field, saved)
    env.space.save(update_fields=[field])
    restored = prepare(env, data)
    assert restored.status_code == 200
    assert restored.data == first.data
    assert snapshot() == before


def test_free_legacy_post_retry_keeps_provider_bound_below_the_tenant_ceiling(free_upload, monkeypatch):
    env, data, provider, clock, identity = free_upload
    value = replace(contract(), identity=identity, max_object_bytes=3, presign_methods=frozenset({"post"}))
    monkeypatch.setattr(runtime, "configured_contracts", lambda: {"private": value})
    monkeypatch.setattr(storage, "configured_contracts", lambda: {"private": value})
    proof = StorageCapabilityState.objects.get(identity_fingerprint=identity.fingerprint)
    proof.configuration_fingerprint = value.fingerprint
    proof.facts = {"presign_methods": ["post"]}
    proof.save(update_fields=["configuration_fingerprint", "facts"])
    provider.generate_presigned_post.return_value = {"url": "https://storage.test/post", "fields": {}}
    data["evidence"].pop("size")
    first = prepare(env, data)
    assert first.status_code == 200, first.data
    before = snapshot()
    again = prepare(env, data)
    assert again.status_code == 200, again.data
    assert again.data == first.data
    assert snapshot() == before
    tenant = StorageQuotaReservation.objects.get(makerspace=env.space)
    cloud = CloudObjectReservation.objects.get()
    assert (tenant.size_bytes, cloud.bytes, tenant.expires_at, cloud.expires_at) == (
        4, 3, clock.now + timedelta(seconds=300), clock.now + timedelta(seconds=300))
    assert provider.generate_presigned_post.call_count == 2
    for call in provider.generate_presigned_post.call_args_list:
        assert call.kwargs["Conditions"] == [{"Content-Type": "image/jpeg"}, ["content-length-range", 1, 3]]
    provider.generate_presigned_url.assert_not_called()

"""First authorizations and pre-reservation retries retain fitting evidence debt."""
from datetime import timedelta
from unittest.mock import Mock

import pytest

from apps.audit.models import AuditLog
from apps.evidence.models import EvidencePhoto, EvidenceObjectRetentionState, EvidenceUploadFinalization
from apps.hardware_requests.models import ReplayCommand
from apps.makerspaces.models import StorageQuotaReservation
from apps.makerspaces.storage_reservation_cleanup import cleanup
from apps.makerspaces.storage_reservations import reserved_bytes
from tests.hardware_requests.replay_helpers import prepare, replay_env
from tests.hardware_requests.test_kiosk_upload_retry_cx7_r3 import (
    assert_post, audit_counts, command, state, upload_env,
)
from tests.return_helpers import make_issue_evidence

pytestmark = [pytest.mark.django_db, pytest.mark.area_lending, pytest.mark.area_inventory]


@pytest.mark.parametrize("method", ["post", "put"])
def test_slow_first_signature_keeps_debt_past_the_original_expiry(upload_env, monkeypatch, settings, method):
    env, provider, clock, transport = upload_env
    transport(method)
    former_expiry = clock.now + timedelta(seconds=300)

    def sign(*args, **kwargs):
        clock.now += timedelta(seconds=7)
        return {"url": "https://storage.test/upload", "fields": {}} if method == "post" else "https://storage.test/put"
    signer = provider.generate_presigned_post if method == "post" else provider.generate_presigned_url
    signer.side_effect = sign
    response = prepare(env, command(env, size=4))
    assert response.status_code == 200, response.data
    row = StorageQuotaReservation.objects.get()
    photo = EvidencePhoto.objects.get()
    owner = ReplayCommand.objects.get()
    assert (row.size_bytes, row.expires_at, row.converted, row.cleaning, row.released) == (
        4, former_expiry + timedelta(seconds=7), False, False, False)
    assert (row.object_key, photo.object_key, owner.evidence_id) == (photo.object_key, photo.object_key, photo.pk)
    assert response.data["upload"]["evidence_id"] == photo.pk
    assert photo.size_bytes == 4 and photo.uploaded_by_id == env.user.pk
    assert signer.call_args.kwargs["ExpiresIn"] == settings.EVIDENCE_URL_TTL_SECONDS == 300
    policy = signer.call_args.kwargs
    if method == "post":
        assert policy["Conditions"] == [{"Content-Type": "image/jpeg"}, ["content-length-range", 1, 4]]
    else:
        assert policy["Params"]["ContentLength"] == 4
    before = state()
    deletion = Mock()
    monkeypatch.setattr("apps.object_storage.delete_all_versions", deletion)
    assert cleanup(row.pk, now=former_expiry) is False
    deletion.assert_not_called()
    assert state() == before
    assert reserved_bytes(env.space) == 4
    assert EvidenceObjectRetentionState.objects.filter(evidence=photo).count() == 0
    assert audit_counts() == (1, 1)
    assert AuditLog.objects.filter(makerspace=env.space, action="storage.upload_reservation_released").count() == 0


@pytest.mark.parametrize("budget,used", [
    ("upload_bytes", 0), ("storage", 0), ("storage_evidence_bytes", 0),
    ("storage", 6), ("storage_evidence_bytes", 6),
])
def test_undeclared_legacy_retry_reserves_the_fitting_remainder(upload_env, settings, budget, used):
    env, provider, clock, _ = upload_env
    data = command(env)
    first = prepare(env, data)
    assert first.status_code == 200, first.data
    StorageQuotaReservation.objects.all().delete()  # Retained pre-reservation command.
    if used:
        other = make_issue_evidence(env.space, env.user)
        EvidenceUploadFinalization.objects.create(evidence=other, status="finalized", size_bytes=used, quota_charged=True)
    env.space.storage_bytes_used = used
    env.space.resource_limit_overrides = {budget: 4 + used}
    env.space.save(update_fields=["resource_limit_overrides", "storage_bytes_used"])
    before = state()
    provider.reset_mock()
    response = prepare(env, data)
    assert response.status_code == 200, response.data
    assert response.data == first.data
    row = StorageQuotaReservation.objects.get()
    assert (row.size_bytes, row.expires_at, row.converted, row.cleaning, row.released) == (
        4, clock.now + timedelta(seconds=300), False, False, False)
    assert_post(provider, row, settings, count=1)
    assert list(ReplayCommand.objects.values()) == before[0]
    assert list(EvidencePhoto.objects.values()) == before[1]
    assert list(AuditLog.objects.order_by("pk").values()) == before[3]
    assert EvidencePhoto.objects.get(pk=response.data["upload"]["evidence_id"]).size_bytes is None
    assert audit_counts() == (1, 1)


@pytest.mark.parametrize("budget,status,code", [
    ("storage", 400, "limit_reached"),
    ("storage_evidence_bytes", 409, "storage_evidence_bytes_quota_reached"),
])
def test_undeclared_legacy_retry_with_no_capacity_never_signs(upload_env, budget, status, code):
    env, provider, _, _ = upload_env
    data = command(env)
    assert prepare(env, data).status_code == 200
    StorageQuotaReservation.objects.all().delete()
    env.space.resource_limit_overrides = {budget: 0}
    env.space.save(update_fields=["resource_limit_overrides"])
    before = state()
    provider.reset_mock()
    response = prepare(env, data)
    assert (response.status_code, response.data["code"]) == (status, code)
    assert state() == before
    provider.generate_presigned_post.assert_not_called()
    provider.generate_presigned_url.assert_not_called()
    assert StorageQuotaReservation.objects.count() == 0
    assert audit_counts() == (1, 1)


def test_undeclared_legacy_retry_on_put_only_storage_retains_typed_refusal(upload_env):
    env, provider, _, transport = upload_env
    data = command(env)
    assert prepare(env, data).status_code == 200
    StorageQuotaReservation.objects.all().delete()
    transport("put")
    before = state()
    provider.reset_mock()
    refused = prepare(env, data)
    assert (refused.status_code, refused.data["code"]) == (400, "upload_size_required")
    assert state() == before
    provider.generate_presigned_post.assert_not_called()
    provider.generate_presigned_url.assert_not_called()


def test_failed_slow_first_signing_rolls_back_command_photo_receipt_and_audits(upload_env):
    from botocore.exceptions import ClientError
    env, provider, clock, _ = upload_env
    before = state()
    def fail(**kwargs):
        clock.now += timedelta(seconds=7)
        raise ClientError({"Error": {"Code": "AccessDenied"}}, "presign")
    provider.generate_presigned_post.side_effect = fail
    refused = prepare(env, command(env, size=4))
    assert (refused.status_code, refused.data["code"]) == (503, "storage_unavailable")
    assert state() == before
    assert audit_counts() == (0, 0)


@pytest.mark.parametrize("declared", [None, 4])
def test_retained_replay_signer_fixture_accepts_the_explicit_size_contract(replay_env, settings, monkeypatch, declared):
    from apps.evidence import services_upload
    from apps.hardware_requests import replay_prepare
    env = replay_env
    settings.EVIDENCE_MAX_BYTES = 10
    signer = Mock(wraps=services_upload.presigned_upload)
    monkeypatch.setattr(services_upload, "presigned_upload", signer)
    monkeypatch.setattr(replay_prepare, "presigned_upload", signer)
    data = command(env, **({"size": declared} if declared is not None else {}))
    first, retry = prepare(env, data), prepare(env, data)
    assert first.status_code == retry.status_code == 200, (first.data, retry.data)
    assert first.data == retry.data
    photo = EvidencePhoto.objects.get()
    maximum = declared or 10
    assert signer.call_count == 2
    assert signer.call_args_list[0].args == signer.call_args_list[1].args == (photo.object_key, "image/jpeg")
    assert signer.call_args_list[0].kwargs == {
        "max_bytes": maximum, **({"exact_bytes": declared} if declared is not None else {})}
    assert signer.call_args_list[1].kwargs == {"max_bytes": maximum, "exact_bytes": declared}
    assert first.data["upload"]["fields"] == {"key": "staging/" + photo.object_key, "Content-Type": "image/jpeg"}
    assert (ReplayCommand.objects.count(), EvidencePhoto.objects.count(), StorageQuotaReservation.objects.count()) == (1, 1, 1)
    assert StorageQuotaReservation.objects.get().size_bytes == maximum
    assert photo.size_bytes == declared
    assert audit_counts() == (1, 1)

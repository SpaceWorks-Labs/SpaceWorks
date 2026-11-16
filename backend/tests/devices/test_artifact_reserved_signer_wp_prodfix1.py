"""Artifact HTTP admission keeps real tenant and physical storage reservations."""
from datetime import timedelta
from io import BytesIO

import pytest
from botocore.exceptions import ClientError
from django.db import connection
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.devices.models import AdapterArtifact
from apps.makerspaces.models import StorageQuotaReservation
from apps.operations.cloud_quotas import storage as capacity
from apps.operations.models import CloudObjectReservation
from tests.devices.test_cross_audit_media_limits_cx9_wp2 import scenario
from tests.machines.test_presign_admission_cx7_r2 import world as signing_world
from tests.modules.switch_matrix_object_helpers import response_pair
from tests.machines.test_document_deletion_wp_prodfix2 import recompute, used

pytestmark = [pytest.mark.django_db, pytest.mark.area_devices]


def test_artifact_real_signer_keeps_private_class_tenant_and_physical_debt(settings, monkeypatch):
    _, _, _, _, provider = signing_world(settings, monkeypatch)
    case, body = scenario(size=4)
    response = case["sim"].post("artifacts", body)
    assert response_pair(response) == (201, None)
    row = AdapterArtifact.objects.get(pk=response.data["artifact_id"])
    debt = StorageQuotaReservation.objects.get(object_key=row.object_key)
    assert (debt.makerspace_id, debt.size_bytes, debt.kind, debt.bucket, debt.final_bucket) == (
        case["space"].pk, 4, "public_image", settings.AWS_STORAGE_BUCKET_NAME, settings.AWS_STORAGE_BUCKET_NAME)
    assert debt.staging_key == "staging/" + row.object_key
    assert row.object_key.startswith(f"adapter-artifacts/{case['space'].pk}/{case['binding_id']}/")
    physical = CloudObjectReservation.objects.get()
    assert (physical.bytes, physical.state, physical.server_owned) == (4, "reserved", False)
    assert physical.key == capacity.object_digest(physical.account_id, debt.staging_key)
    assert response.data["upload"]["method"] == "PUT"
    assert provider.generate_presigned_url.call_args.kwargs["Params"] == {
        "Bucket": settings.AWS_STORAGE_BUCKET_NAME, "Key": debt.staging_key,
        "ContentType": "image/jpeg", "ContentLength": 4, "IfNoneMatch": "*"}
    provider.generate_presigned_post.assert_not_called()
    assert AuditLog.objects.filter(makerspace=case["space"], action="devices.adapter_artifact_requested").count() == 1


@pytest.mark.parametrize("refusal", ["capacity", "unproven", "provider_ceiling"])
def test_artifact_real_signer_provider_refusal_rolls_back_domain_and_tenant_debt(refusal, settings, monkeypatch):
    _, _, _, _, provider = signing_world(settings, monkeypatch, refusal)
    case, body = scenario(size=4)
    before = list(AuditLog.objects.order_by("pk").values())
    response = case["sim"].post("artifacts", body)
    assert response_pair(response) == (503, "storage_unavailable")
    assert AdapterArtifact.objects.count() == 0
    assert StorageQuotaReservation.objects.count() == 0
    assert CloudObjectReservation.objects.count() == 0
    assert list(AuditLog.objects.order_by("pk").values()) == before
    provider.generate_presigned_url.assert_not_called()


@pytest.mark.parametrize("limit,status,code", [
    ("storage", 400, "limit_reached"), ("upload_bytes", 400, "upload_limit"),
    ("storage_public_images_bytes", 409, "storage_public_images_bytes_quota_reached"),
])
def test_artifact_real_signer_refuses_tenant_storage_limits_before_provider(limit, status, code, settings, monkeypatch):
    _, _, _, _, provider = signing_world(settings, monkeypatch)
    case, body = scenario(size=4)
    case["space"].resource_limit_overrides = {limit: 3}
    case["space"].save(update_fields=["resource_limit_overrides"])
    before = list(AuditLog.objects.order_by("pk").values())
    response = case["sim"].post("artifacts", body)
    assert response_pair(response) == (status, code)
    assert AdapterArtifact.objects.count() == 0
    assert StorageQuotaReservation.objects.count() == 0
    assert CloudObjectReservation.objects.count() == 0
    assert list(AuditLog.objects.order_by("pk").values()) == before
    provider.generate_presigned_url.assert_not_called()


def real_artifact(settings, monkeypatch, *, ready=True):
    """Real reserved signing, promotion and confirmed deletion; only the SDK is doubled."""
    _, _, _, _, provider = signing_world(settings, monkeypatch)
    from apps.storage_capabilities.runtime import capabilities_for
    monkeypatch.setattr("apps.object_storage.capabilities_for", capabilities_for)
    case, body = scenario(size=4)
    first = case["sim"].post("artifacts", body)
    assert response_pair(first) == (201, None)
    row = AdapterArtifact.objects.get(pk=first.data["artifact_id"])
    debt = StorageQuotaReservation.objects.get(object_key=row.object_key)
    objects, failing = {debt.staging_key: b"jpeg"}, set()

    def head(*, Bucket, Key):
        if Key not in objects:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "HeadObject")
        return {"ContentLength": len(objects[Key]), "ContentType": "image/jpeg", "ETag": '"snapshot"'}

    def put(*, Bucket, Key, Body, **kwargs):
        assert connection.in_atomic_block is False
        objects[Key] = Body.read()
        return {}

    def delete(*, Bucket, Key):
        if Key in failing:
            raise ClientError({"Error": {"Code": "AccessDenied"}}, "DeleteObject")
        objects.pop(Key, None)
        return {}

    provider.head_object.side_effect = head
    provider.get_object.side_effect = lambda **kw: {"Body": BytesIO(objects[kw["Key"]]), "ContentType": "image/jpeg"}
    provider.put_object.side_effect = put
    provider.delete_object.side_effect = delete
    if ready:
        completed = case["sim"].post(f"artifacts/{row.pk}/complete")
        assert response_pair(completed) == (200, None)
        row.refresh_from_db()
        debt.refresh_from_db()
        assert (row.status, row.size_bytes, debt.converted, debt.released) == ("ready", 4, True, False)
    return case, body, first, row, debt, provider, objects, failing


@pytest.mark.django_db(transaction=True)
def test_real_signer_completion_survives_url_expiry_and_retains_charge_until_both_keys_deleted(settings, monkeypatch):
    from apps.devices.services_adapter_artifacts import purge_expired
    from apps.makerspaces.storage_reservation_cleanup import cleanup
    from apps.makerspaces.storage_reservations import reserved_bytes

    case, _, _, row, debt, _, objects, failing = real_artifact(settings, monkeypatch)
    assert (used(case["space"]), reserved_bytes(case["space"])) == (4, 0)
    assert objects == {row.object_key: b"jpeg"}
    completed_again = case["sim"].post(f"artifacts/{row.pk}/complete")
    assert response_pair(completed_again) == (200, None)
    assert AuditLog.objects.filter(action="devices.adapter_artifact_stored", makerspace=case["space"]).count() == 1
    assert cleanup(debt.pk, now=debt.expires_at + timedelta(seconds=1)) is False
    assert objects == {row.object_key: b"jpeg"}
    recompute(case["space"], 4)
    recompute(case["space"], 4)
    # An original staging authorization can leave late bytes after promotion.
    objects[debt.staging_key] = b"late"
    failing.add(debt.staging_key)
    due = row.expires_at + timedelta(seconds=1)
    assert purge_expired(now=due, space_id=case["space"].pk) == 0
    row.refresh_from_db()
    debt.refresh_from_db()
    assert (row.status, used(case["space"]), debt.released, debt.cleaning) == ("ready", 4, False, True)
    assert objects == {debt.staging_key: b"late"}
    recompute(case["space"], 4)
    failing.clear()
    assert purge_expired(now=due, space_id=case["space"].pk) == 1
    row.refresh_from_db()
    debt.refresh_from_db()
    assert (row.status, row.size_bytes, used(case["space"]), debt.released, debt.cleaning) == ("purged", 4, 0, True, False)
    assert objects == {}
    assert AuditLog.objects.filter(action="devices.adapter_artifact_purged", makerspace=case["space"]).count() == 1
    assert purge_expired(now=due, space_id=case["space"].pk) == 0
    recompute(case["space"], 0)
    recompute(case["space"], 0)


@pytest.mark.django_db(transaction=True)
def test_real_signer_pending_replay_keeps_original_tenant_and_physical_authorization(settings, monkeypatch):
    from apps.machines.service_storage import presigned_upload
    from rest_framework.exceptions import ValidationError

    case, body, first, row, debt, provider, _, _ = real_artifact(settings, monkeypatch, ready=False)
    tenant_before = StorageQuotaReservation.objects.values().get(pk=debt.pk)
    physical_before = list(CloudObjectReservation.objects.values())
    replay = case["sim"].post("artifacts", body)
    assert response_pair(replay) == (201, None)
    assert (replay.data["artifact_id"], replay.data["duplicate"]) == (first.data["artifact_id"], True)
    assert replay.data["object_key"] == first.data["object_key"]
    assert replay.data["upload"]["headers"] == first.data["upload"]["headers"]
    assert StorageQuotaReservation.objects.values().get(pk=debt.pk) == tenant_before
    assert list(CloudObjectReservation.objects.values()) == physical_before
    assert (StorageQuotaReservation.objects.count(), CloudObjectReservation.objects.count(), used(case["space"])) == (1, 1, 0)
    assert provider.generate_presigned_url.call_count == 2
    assert provider.generate_presigned_url.call_args.kwargs["ExpiresIn"] < settings.EVIDENCE_URL_TTL_SECONDS
    assert AuditLog.objects.filter(action="devices.adapter_artifact_requested", makerspace=case["space"]).count() == 1
    with pytest.raises(ValidationError) as refused:
        presigned_upload(row.object_key, row.content_type, 5 * 2**20, exact_bytes=4)
    assert (refused.value.status_code, refused.value.detail["code"]) == (400, "upload_limit")


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("state", ["released", "converted", "expired", "wrong_size", "wrong_bucket", "wrong_class"])
def test_real_signer_replay_refuses_nonmatching_or_spent_authorization(state, settings, monkeypatch):
    case, body, _, _, debt, provider, _, _ = real_artifact(settings, monkeypatch, ready=False)
    changes = {"released": {"released": True}, "converted": {"converted": True},
        "expired": {"expires_at": timezone.now() - timedelta(seconds=1)}, "wrong_size": {"size_bytes": 5},
        "wrong_bucket": {"bucket": "other-bucket"}, "wrong_class": {"kind": "evidence"}}[state]
    StorageQuotaReservation.objects.filter(pk=debt.pk).update(**changes)
    before = StorageQuotaReservation.objects.values().get(pk=debt.pk)
    physical = list(CloudObjectReservation.objects.values())
    replay = case["sim"].post("artifacts", body)
    assert response_pair(replay) == (400, "upload_limit")
    assert StorageQuotaReservation.objects.values().get(pk=debt.pk) == before
    assert list(CloudObjectReservation.objects.values()) == physical
    assert provider.generate_presigned_url.call_count == 1


@pytest.mark.django_db(transaction=True)
def test_completion_provider_failure_retains_admission_and_successful_retry_charges_once(settings, monkeypatch):
    from botocore.exceptions import EndpointConnectionError
    from apps.makerspaces.storage_reservations import reserved_bytes

    case, _, _, row, debt, provider, _, _ = real_artifact(settings, monkeypatch, ready=False)
    put = provider.put_object.side_effect
    provider.put_object.side_effect = EndpointConnectionError(endpoint_url="https://timeout.test")
    failed = case["sim"].post(f"artifacts/{row.pk}/complete")
    assert response_pair(failed) == (503, "storage_unavailable")
    row.refresh_from_db()
    debt.refresh_from_db()
    assert (row.status, debt.converted, debt.released, used(case["space"]), reserved_bytes(case["space"])) == (
        "pending", False, False, 0, 4)
    assert AuditLog.objects.filter(action="devices.adapter_artifact_stored", makerspace=case["space"]).count() == 0
    provider.put_object.side_effect = put
    success = case["sim"].post(f"artifacts/{row.pk}/complete")
    assert response_pair(success) == (200, None)
    row.refresh_from_db()
    debt.refresh_from_db()
    assert (row.status, debt.converted, used(case["space"]), reserved_bytes(case["space"])) == ("ready", True, 4, 0)
    assert AuditLog.objects.filter(action="devices.adapter_artifact_stored", makerspace=case["space"]).count() == 1


@pytest.mark.django_db(transaction=True)
def test_completion_cannot_manufacture_a_missing_upload_admission(settings, monkeypatch):
    case, _, _, row, debt, provider, _, _ = real_artifact(settings, monkeypatch, ready=False)
    debt.delete()
    failed = case["sim"].post(f"artifacts/{row.pk}/complete")
    assert response_pair(failed) == (400, "upload_limit")
    assert not StorageQuotaReservation.objects.filter(object_key=row.object_key).exists()
    assert used(case["space"]) == 0
    assert AuditLog.objects.filter(action="devices.adapter_artifact_stored", makerspace=case["space"]).count() == 0
    provider.put_object.assert_not_called()

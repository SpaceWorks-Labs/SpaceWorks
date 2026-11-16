"""Machine uploads acquire both deployment capacity and tenant byte debt."""
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.machines import job_files, service_storage
from apps.machines.models import MachineServiceRequest, MachineType, ServiceQueue, ServiceRequestFile
from apps.makerspaces.models import StorageQuotaReservation
from apps.operations.cloud_quotas import storage as capacity
from apps.operations.models import CloudObjectAccount, CloudObjectReservation
from apps.storage_capabilities import presigning, runtime, verification
from apps.evidence.storage import StorageUnavailable
from apps.evidence.responses import storage_unavailable_response
from tests.cloud.storage.test_contracts import contract
from tests.return_helpers import make_member, make_space

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_machine_service,
              pytest.mark.area_machines]


def world(settings, monkeypatch, refusal=None):
    settings.MANAGED_PLANS_ENABLED = False
    settings.STORAGE_CAPABILITIES_FILE = "proven-machine-contract"
    settings.STORAGE_PRESIGN_METHOD = "auto"
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "free"
    settings.SPACEWORKS_DEPLOYMENT_MODE = "host"
    settings.FREE_OBJECT_CAP_BYTES = 3 if refusal == "capacity" else 4
    settings.FREE_MAX_PROMOTION_BYTES = 8
    value = contract(max_object_bytes=3 if refusal == "provider_ceiling" else 8)
    facts = {"presign_methods": ["put"], "conditional_create": True, "put_conditional_presign": True}
    if refusal == "unsupported":
        settings.STORAGE_PRESIGN_METHOD = "post"
    elif refusal == "unproven":
        facts["presign_methods"] = []
    elif refusal == "replayable_post":
        settings.STORAGE_PRESIGN_METHOD = "post"
        value = replace(value, presign_methods=frozenset({"post"}), versioning="enabled")
        facts["presign_methods"] = ["post"]
    for module in (presigning, runtime):
        monkeypatch.setattr(module, "capabilities_for", lambda *a, **kw: value)
    for module in (presigning, verification):
        monkeypatch.setattr(module, "verified_state", lambda *a: SimpleNamespace(facts=facts))
    monkeypatch.setattr(runtime, "configured_contracts", lambda: {"private": value})
    monkeypatch.setattr(capacity, "identity_for", lambda *a: value.identity.fingerprint)
    CloudObjectAccount.objects.create(identity=value.identity.fingerprint, used=0, sampled_at=timezone.now(), reason="")
    provider = Mock(meta=SimpleNamespace(endpoint_url="https://storage.test"))
    provider.generate_presigned_url.return_value = "https://storage.test/put"
    monkeypatch.setattr(service_storage, "_public_client", lambda: provider)
    monkeypatch.setattr(service_storage, "_client", lambda: provider)
    space = make_space("r2-machine-admission")
    actor = make_member("r2-machine-uploader", space)
    kind = MachineType.objects.create(makerspace=space, name="Laser", slug="r2-laser")
    queue = ServiceQueue.objects.create(makerspace=space, machine_type=kind, name="Laser jobs")
    # Format resolution is independent of storage admission; exercise all real creators
    # while fixing only their file-policy input to the same bounded declaration.
    policy = SimpleNamespace(name="documents", version=1, max_bytes=8,
                             allowed_extensions=("pdf",), allowed_mimes=("application/pdf",))
    monkeypatch.setattr(service_storage, "policy_for_queue", lambda *a: policy)
    monkeypatch.setattr(job_files, "resolve", lambda *a: (SimpleNamespace(preview=False), 8, "documents"))
    request = MachineServiceRequest.objects.create(makerspace=space, queue=queue, requester=actor, title="Repair")
    return space, actor, queue, request, provider


def stage(kind, world):
    space, actor, queue, request, provider = world
    body = {"filename": "manual.pdf", "content_type": "application/pdf", "size": 4}
    if kind == "job":
        return job_files.stage_job_file(queue, actor, kind="model", **body)
    if kind == "queue":
        return service_storage.create_staged_queue_file(queue, actor=actor, **body)
    return service_storage.create_staged_file(request, actor=actor, **body)


@pytest.mark.parametrize("kind", ["job", "queue", "attachment"])
def test_machine_creators_take_the_deployment_reservation_and_exact_tenant_debt(kind, settings, monkeypatch):
    setup = world(settings, monkeypatch)
    upload, result, *_ = stage(kind, setup)
    assert result["method"] == "PUT"
    assert result["headers"]["Content-Length"] == "4"
    tenant = StorageQuotaReservation.objects.get(object_key=upload.object_key)
    assert (tenant.size_bytes, tenant.converted, tenant.released) == (4, False, False)
    physical = CloudObjectReservation.objects.get()
    assert (physical.bytes, physical.state, physical.server_owned) == (4, "reserved", False)
    assert physical.key == capacity.object_digest(physical.account_id, tenant.staging_key)
    params = setup[-1].generate_presigned_url.call_args.kwargs["Params"]
    assert params == {"Bucket": settings.AWS_STORAGE_BUCKET_NAME, "Key": tenant.staging_key,
                      "ContentType": "application/pdf", "ContentLength": 4, "IfNoneMatch": "*"}
    setup[-1].generate_presigned_post.assert_not_called()
    assert AuditLog.objects.filter(action="machine_service.file_staged", makerspace=setup[0]).count() == 1


@pytest.mark.parametrize("kind", ["job", "queue", "attachment"])
@pytest.mark.parametrize("refusal,code", [
    ("unsupported", "storage_presign_method_unsupported"),
    ("unproven", "storage_presign_method_unproven"),
    ("replayable_post", "storage_free_replayable_post_refused"),
    ("capacity", "storage_account_cap_reached"),
    ("provider_ceiling", "storage_provider_object_limit_exceeded"),
])
def test_machine_creators_refuse_before_policy_and_preserve_domain_quota_and_audit(kind, refusal, code, settings, monkeypatch):
    setup = world(settings, monkeypatch, refusal)
    audits = list(AuditLog.objects.order_by("pk").values())
    accounts = list(CloudObjectAccount.objects.order_by("pk").values())
    with pytest.raises(StorageUnavailable) as error:
        stage(kind, setup)
    assert error.value.__cause__.code == code
    response = storage_unavailable_response()
    assert (response.status_code, response.data["code"]) == (503, "storage_unavailable")
    assert not ServiceRequestFile.objects.exists()
    assert not StorageQuotaReservation.objects.exists()
    assert not CloudObjectReservation.objects.exists()
    assert list(CloudObjectAccount.objects.order_by("pk").values()) == accounts
    assert list(AuditLog.objects.order_by("pk").values()) == audits
    setup[-1].generate_presigned_url.assert_not_called()
    setup[-1].generate_presigned_post.assert_not_called()

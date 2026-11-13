"""Decision 246 (lane F8): idempotency and audit conditions for the machine job intake (221e)."""
import pytest

from apps.audit.models import AuditLog
from apps.machines.models import MachineServiceRequest, MakerspaceMachineTypePolicy, ServiceRequestFile
from tests.machines.eta_helpers import world
from tests.machines.test_job_intake import admitted, storage, submit, upload  # noqa: F401
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db


def _ready(slug):
    w = world(slug)
    return w, authenticated_client(admitted(w, f"{slug}-m"))


def test_a_submitted_job_writes_one_submitted_audit_row_and_one_staged_row_per_file(storage):
    w, client = _ready("f8-221e-aud")
    file_id = upload(client, w).json()["file_id"]
    assert AuditLog.objects.filter(makerspace=w.space, action="machine_service.file_staged").count() == 1
    created = submit(client, w, [file_id])
    assert created.status_code == 201, created.content
    job = MachineServiceRequest.objects.get(public_token=created.json()["public_token"])
    row = AuditLog.objects.get(makerspace=w.space, action="machine_service.submitted")
    assert row.meta["request_id"] == job.pk and row.meta["status"] == "pending"


def test_a_refused_submission_writes_no_submitted_audit_row(storage):
    w, client = _ready("f8-221e-refused")
    file_id = upload(client, w).json()["file_id"]
    assert submit(client, w, [file_id], acknowledgements={}).status_code == 400
    assert not AuditLog.objects.filter(makerspace=w.space, action="machine_service.submitted").exists()
    assert not MachineServiceRequest.objects.filter(makerspace=w.space).exists()


def test_a_repeated_file_id_attaches_once(storage):
    w, client = _ready("f8-221e-dup")
    file_id = upload(client, w).json()["file_id"]
    created = submit(client, w, [file_id, file_id])
    assert created.status_code == 201, created.content
    job = MachineServiceRequest.objects.get(public_token=created.json()["public_token"])
    assert ServiceRequestFile.objects.filter(service_request=job).count() == 1


def test_resubmitting_an_attached_file_never_makes_a_second_job_with_the_open_job_limit_on(storage):
    w, client = _ready("f8-221e-replay")
    MakerspaceMachineTypePolicy.objects.create(makerspace=w.space, machine_type=w.kind, max_open_jobs=1)
    file_id = upload(client, w).json()["file_id"]
    assert submit(client, w, [file_id]).status_code == 201
    again = submit(client, w, [file_id])
    assert again.status_code in (400, 404, 409, 422)
    assert MachineServiceRequest.objects.filter(makerspace=w.space).count() == 1
    assert AuditLog.objects.filter(makerspace=w.space, action="machine_service.submitted").count() == 1


def test_one_members_files_cannot_be_attached_to_another_members_job(storage):
    w, client = _ready("f8-221e-owner")
    other = authenticated_client(admitted(w, "f8-221e-other"))
    file_id = upload(client, w).json()["file_id"]
    refused = submit(other, w, [file_id])
    assert refused.status_code in (400, 403, 404, 409, 422)
    assert not MachineServiceRequest.objects.filter(makerspace=w.space).exists()

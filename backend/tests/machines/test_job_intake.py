"""#140/#142 OQ-1/OQ-10/OQ-12/OQ-16: one "Request a job" intake for every machine type."""

import pytest

from apps.machines.models import MachineServiceRequest, MakerspaceMachineTypePolicy, ServiceRequestFile
from apps.machines.service_storage import ServiceObjectValidationResult
from tests.machines.eta_helpers import enable, owner, world
from tests.machines.session_helpers import check_in
from tests.rbac_f6_helpers import community_member
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db
def admitted(w, name):
    enable(w.space, "membership", "presence")
    membership = community_member(w.space, name)
    check_in(w.space, membership)
    return membership.user


ACK = {"pickup_policy": True, "failure_policy": True, "own_content": True}


@pytest.fixture
def storage(monkeypatch):
    monkeypatch.setattr("apps.machines.service_storage.presigned_upload", lambda *args: {"url": "https://upload.test"})
    monkeypatch.setattr("apps.machines.job_files.validate_job_object",
                        lambda file: ServiceObjectValidationResult(size=10, content_type=file.content_type))


def upload(client, w, filename="part.svg", content_type="image/svg+xml", kind="model"):
    return client.post(f"/api/v1/public/{w.space.slug}/machine-jobs/uploads",
                       {"queue_id": w.queue.pk, "filename": filename, "content_type": content_type, "kind": kind},
                       format="json")


def submit(client, w, file_ids, **extra):
    body = {"queue_id": w.queue.pk, "title": "Coasters", "file_ids": file_ids, "copies": 4, "acknowledgements": ACK}
    body.update(extra)
    return client.post(f"/api/v1/public/{w.space.slug}/machine-jobs", body, format="json")


def test_types_list_formats_and_a_member_submits_a_laser_job(storage):
    w = world("intake-laser")
    member = admitted(w, "intake-member")
    types = authenticated_client(owner("intake-anon")).get(f"/api/v1/public/{w.space.slug}/machine-jobs/types")
    assert types.status_code == 200, types.content
    row = next(item for item in types.json() if item["queue_id"] == w.queue.pk)
    assert "svg" in row["accepted_extensions"]
    client = authenticated_client(member)
    staged = upload(client, w)
    assert staged.status_code == 201, staged.content
    assert upload(client, w, filename="virus.exe", content_type="application/octet-stream").status_code == 400
    created = submit(client, w, [staged.json()["file_id"]], needed_by="2030-01-01", own_material=True)
    assert created.status_code == 201, created.content
    job = MachineServiceRequest.objects.get(public_token=created.json()["public_token"])
    assert (job.member_id, job.copies, job.own_material, job.status) == (member.pk, 4, True, "pending")
    assert ServiceRequestFile.objects.filter(service_request=job).count() == 1
    mine = client.get("/api/v1/member/machine-jobs").json()
    assert [item["id"] for item in mine] == [job.pk] and mine[0]["label"] == "submitted"


def test_acknowledgements_and_a_design_file_are_required(storage):
    w = world("intake-rules")
    client = authenticated_client(admitted(w, "intake-rules-m"))
    shot = upload(client, w, filename="photo.png", content_type="image/png", kind="screenshot").json()["file_id"]
    assert submit(client, w, [shot], acknowledgements={"pickup_policy": True}).status_code == 400
    assert submit(client, w, [shot]).status_code == 400  # screenshots alone are not a job
    assert submit(client, w, []).status_code == 400


def test_switch_type_setting_and_open_job_limit(storage):
    w = world("intake-gates")
    client = authenticated_client(admitted(w, "intake-gates-m"))
    MakerspaceMachineTypePolicy.objects.create(makerspace=w.space, machine_type=w.kind, max_open_jobs=1)
    first = upload(client, w).json()["file_id"]
    assert submit(client, w, [first]).status_code == 201
    second = upload(client, w).json()["file_id"]
    refused = submit(client, w, [second])
    assert refused.status_code == 409 and "job_limit_reached" in str(refused.content)
    MakerspaceMachineTypePolicy.objects.filter(machine_type=w.kind).update(accepts_job_requests=False, max_open_jobs=None)
    assert submit(client, w, [second]).status_code == 400
    w.space.enabled_features = [key for key in w.space.enabled_features if key != "machines.job_requests"]
    w.space.save(update_fields=["enabled_features"])
    assert client.get(f"/api/v1/public/{w.space.slug}/machine-jobs/types").status_code == 404


def test_checked_in_membership_is_required_when_membership_is_on(storage):
    w = world("intake-presence", membership=True)
    enable(w.space, "presence")
    client = authenticated_client(owner("intake-presence-m"))
    assert upload(client, w).status_code == 403


def test_submission_rechecks_module_switch_at_makerspace_lock(storage, monkeypatch):
    w = world("intake-fresh-maker")
    client = authenticated_client(admitted(w, "fresh-member"))
    staged = upload(client, w)
    assert staged.status_code == 201, staged.content
    from apps.machines import job_intake
    original = job_intake._payload

    def disable_presence(queue, data):
        from apps.makerspaces.models import Makerspace
        space = Makerspace.objects.get(pk=w.space.pk)
        space.enabled_modules = [key for key in space.enabled_modules if key != "presence"]
        space.save(update_fields=["enabled_modules"])
        return original(queue, data)

    monkeypatch.setattr(job_intake, "_payload", disable_presence)
    denied = submit(client, w, [staged.json()["file_id"]])
    assert denied.status_code == 404 and denied.json()["code"] == "machine_intake_unavailable"
    assert not MachineServiceRequest.objects.filter(makerspace=w.space).exists()
    assert ServiceRequestFile.objects.get(pk=staged.json()["file_id"]).service_request_id is None

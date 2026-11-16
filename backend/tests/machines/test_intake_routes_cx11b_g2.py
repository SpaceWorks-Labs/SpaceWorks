"""Real upload/submission on all three intake forms; each admission dependency independently off."""
from unittest.mock import Mock

import pytest

from apps.machines import service_storage
from apps.machines.models import MachineServiceRequest, MachineType, ServiceRequestFile
from tests.machines.member_support_cx11b_g2 import member_world
from tests.machines.route_support_cx11b_g2 import command, prove

pytestmark = [pytest.mark.django_db, pytest.mark.area_machines, pytest.mark.area_machine_service]
ROUTES = ["public-machine-job-upload", "public-machine-job-submit", "public-machine-service-request-submit",
          "public-printer-service-upload", "public-printer-service-request"]
KEYS = [("machine_service", "module_disabled"),
        ("machines.job_requests", "feature_disabled"), ("membership", "machine_intake_unavailable"),
        ("presence", "machine_intake_unavailable")]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key,code", KEYS)
@pytest.mark.parametrize("name", ROUTES)
def test_every_intake_creates_a_real_file_or_job_and_rechecks_each_dependency(native, key, code, name, monkeypatch):
    w = member_world(native)
    printer = name.startswith("public-printer")
    uploading = name.endswith("upload")
    if printer:
        w.queue.machine_type = MachineType.objects.get(makerspace__isnull=True, slug="3d_printer")
        w.queue.save(update_fields=["machine_type"])
    presign = Mock(return_value={"url": "https://upload.example.test/job"})
    monkeypatch.setattr(service_storage, "presigned_upload", presign)
    monkeypatch.setattr("apps.machines.job_files.validate_job_object", lambda file:
                        service_storage.ServiceObjectValidationResult(size=13, content_type=file.content_type))
    staged = ServiceRequestFile.objects.create(makerspace=w.space, queue=w.queue, owner_user_id=w.member.pk,
        kind="model", object_key=f"machine-service/{w.space.pk}/g2-design.svg", original_filename="design.svg",
        content_type="image/svg+xml", file_policy_name="maker_formats")
    if uploading:
        body = {"queue_id": w.queue.pk, "filename": "part.stl" if printer else "design.svg",
                "content_type": "model/stl" if printer else "image/svg+xml", "kind": "stl" if printer else "model"}
        audits = ("machine_service.file_staged",)
    elif name == "public-machine-job-submit":
        body = {"queue_id": w.queue.pk, "title": "Restored drawing", "file_ids": [staged.pk], "copies": 2,
                "acknowledgements": {"pickup_policy": True, "failure_policy": True, "own_content": True}}
        audits = ("machine_service.submitted", "machine_service.file_attached")
    elif printer:
        body, audits = {"queue_id": w.queue.pk, "title": "Restored drawing"}, ("machine_service.submitted",)
    else:
        body, audits = {"machine_id": w.machine.pk, "title": "Restored drawing"}, ("machine_service.submitted",)

    def check(response):
        if uploading:
            saved = ServiceRequestFile.objects.get(pk=response.data["file_id"])
            assert (saved.owner_user_id, saved.queue_id, saved.original_filename, saved.service_request_id) == (
                w.member.pk, w.queue.pk, body["filename"], None)
            assert response.data["upload"] == {"url": "https://upload.example.test/job"}
            assert presign.call_args.args[:2] == (saved.object_key, body["content_type"])
            assert ServiceRequestFile.objects.filter(makerspace=w.space).count() == 2
        else:
            saved = MachineServiceRequest.objects.get(public_token=response.data["public_token"])
            assert (saved.title, saved.status, saved.member_id, saved.makerspace_id) == (
                "Restored drawing", "pending", w.member.pk, w.space.pk)
            assert MachineServiceRequest.objects.filter(makerspace=w.space).count() == 1
            if name == "public-machine-job-submit":
                attached = ServiceRequestFile.objects.get(pk=staged.pk)
                assert (attached.service_request_id, attached.size_bytes, saved.copies) == (saved.pk, 13, 2)
                assert attached.attached_at is not None
            elif printer:
                assert saved.queue_id == w.queue.pk
            else:
                assert saved.bucket.machine_id == w.machine.pk

    # Public admission is discoverable (494's personal/public contract); a person
    # without membership gets membership_required while on, and the PUBLIC switch
    # refusal while off. No foreign write is allowed in either state.
    prove(w, key, lambda c: command(c, name, "post", [w.space.slug], body), check,
          status=201, audits=audits, off=(404, code), foreign=(403, "membership_required"), foreign_off=(404, code),
          providers=(presign,) if uploading else ())

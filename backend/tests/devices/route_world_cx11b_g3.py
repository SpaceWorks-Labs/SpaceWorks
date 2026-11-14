"""Real enrolled adapter, scoped target and deterministic retained G3 data."""
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

from django.utils import timezone

from apps.devices.models import (
    AdapterAccessLog, AdapterArtifact, AdapterBinding, AdapterCommand, AdapterConfigVersion,
    AdapterCredential, AdapterEvent, AdapterPose, AdapterTelemetryPoint, AdapterTypeProfile,
    AdapterUsageLog, AdapterWatch, AdapterWebhook, AdapterWebhookDelivery, DeviceCommand, PrinterJob,
)
from apps.machines.models import MachineServiceRequest, ServiceQueue
from tests.modules.switch_matrix_object_helpers import client_for
from tests.parity_0120.adapter_api.adapter_case import adapter_case, plain_member
from tests.maintenance.route_support_cx11b_g3 import foreign_client, person_client
from tests.return_helpers import make_product

BASE_KEYS = ("devices", "machines", "machine_service", "machines.integrations")
CAPS = ("status", "events", "control", "media.stream", "media.snapshot", "media.audio", "media.talk",
        "diagnostics", "job.dispatch", "access.authorize", "usage.log")


def world(native, *, pointer=False):
    c = adapter_case("g3-adapter", caps=CAPS, extra=("locate.calibrate", "locate.indicate"))
    w = SimpleNamespace(**c)
    w.actor = c["manager"]
    w.client = client_for(w.actor, w.space, native)
    w.foreign = foreign_client(native)
    w.member = plain_member("g3-owner", w.space)
    w.second = person_client(plain_member("g3-second-person", w.space), w.space, native)
    w.owner = person_client(w.member, w.space, native)
    w.binding = AdapterBinding.objects.get(pk=c["binding_id"])
    w.now = timezone.now()
    if pointer:
        w.binding = AdapterBinding.objects.create(makerspace=w.space, device=w.device, target_type="space",
            target_id="pointer", capabilities=["locate.calibrate", "locate.indicate"], created_by=w.actor)
    queue = ServiceQueue.objects.create(makerspace=w.space, machine_type=w.machine.machine_type,
                                        name="Retained adapter queue")
    w.job = MachineServiceRequest.objects.create(queue=queue,makerspace=w.space, requester=w.member, member=w.member,
        assigned_machine=w.machine, title="Retained run", status="in_progress",
        started_at=w.now - timedelta(minutes=5))
    w.objects = {"device": w.device, "binding": w.binding, "machine": w.machine, "job": w.job}
    return w


def event(w, kind="detection.reported", data=None):
    return AdapterEvent.objects.create(makerspace=w.space, device=w.device, binding=w.binding,
        operation_id=uuid4(), event_type=kind, capability="events", observed_at=w.now,
        data=data or {"kind": "smoke", "confidence": 0.75, "note": "Staff only"})


def command(w, capability="control", name="pause", params=None):
    return AdapterCommand.objects.create(makerspace=w.space, device=w.device, binding=w.binding,
        device_key_version=w.device.key_version, capability=capability, command=name, params=params or {},
        created_by=w.actor, expires_at=w.now + timedelta(minutes=5))


def watch(w, *, owner=False):
    return AdapterWatch.objects.create(makerspace=w.space, binding=w.binding, viewer=w.member if owner else w.actor,
        expires_at=w.now + timedelta(minutes=5), audio=not owner, talk=not owner, audio_notice_ack=not owner,
        signals=[{"n": 1, "from": "adapter", "kind": "answer", "sdp": "v=0 retained", "candidate": ""}])


def artifact(w, kind="thumbnail"):
    mime = {"audio_recording": "audio/webm", "log_bundle": "application/zip"}.get(kind, "image/jpeg")
    return AdapterArtifact.objects.create(makerspace=w.space, binding=w.binding, operation_id=uuid4(), kind=kind,
        content_type=mime, size_bytes=123, object_key=f"adapter-artifacts/{w.space.pk}/retained.jpg",
        status="ready", service_request_id=w.job.pk, expires_at=w.now + timedelta(days=1))


def hook(w):
    return AdapterWebhook.objects.create(makerspace=w.space, device=w.device, url="https://hooks.example.test/old",
                                        created_by=w.actor)


def credential(w):
    from apps.devices.services_adapter_core import credential_digest
    return AdapterCredential.objects.create(makerspace=w.space, user=w.member, kind="pin", label="Retained PIN",
        digest=credential_digest(w.space.pk, "pin", "739152", user_id=w.member.pk), created_by=w.actor)


def pose(w):
    w.product = make_product(w.space, name="Retained pointer target")
    return AdapterPose.objects.create(makerspace=w.space, binding=w.binding, target_type="item",
        target_id=str(w.product.pk), pose={"pan": 12, "tilt": 3}, note="Retained pose", saved_by=w.actor)


def printer_job(w):
    cmd = DeviceCommand.objects.create(makerspace=w.space, device=w.device, kind="adapter_job",
                                      device_key_version=w.device.key_version, created_by=w.actor)
    return PrinterJob.objects.create(makerspace=w.space, device=w.device, machine=w.machine, command=cmd,
        service_request=w.job, machine_id_snapshot=w.machine.pk, machine_name=w.machine.name,
        service_request_id_snapshot=w.job.pk, service_request_name=w.job.title, external_job_id="retained-run")

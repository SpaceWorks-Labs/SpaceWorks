"""Adapter staff switches: actual bound devices and retained media/data, both transports."""
from datetime import timedelta
from uuid import uuid4

import pytest
from tests.modules.test_switch_matrix_objects_rest_isolation import cx11b_isolated_phase  # noqa: F401
from django.urls import reverse
from django.utils import timezone

from apps.devices.models import AdapterArtifact, AdapterBinding, AdapterEvent, AdapterTelemetryPoint
from tests.inventory.switch_support_cx11b_p1 import prove_route, staff_outsiders
from tests.modules.switch_matrix_object_helpers import client_for
from tests.parity_0120.adapter_api.adapter_case import adapter_case

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_machines, pytest.mark.area_devices]
KINDS = ("integrations", "video", "audio", "talk", "recording", "audio_recording", "artifacts",
         "detections", "telemetry_history", "diagnostics")
CAPS = ("status", "events", "media.stream", "media.audio", "media.talk", "artifact.upload",
        "detection.report", "telemetry", "telemetry.history", "diagnostics")
# Every child also depends on all three installed modules and the integration parent.
SIBLINGS = {"audio": ("video",), "talk": ("video", "audio"), "recording": ("video",),
            "audio_recording": ("video", "audio", "recording")}
CASES = [(kind, key) for kind in KINDS for key in dict.fromkeys((
    "machines.integrations" if kind == "integrations" else f"machines.integrations.{kind}",
    "machines.integrations", "machines", "devices", "machine_service",
    *(f"machines.integrations.{child}" for child in SIBLINGS.get(kind, ()))))]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("kind,key", CASES)
def test_bound_adapter_switch_refuses_without_writes_and_restores_data(kind, key, native):
    case = adapter_case("p1-adapter", caps=CAPS)
    space, actor = case["space"], case["manager"]
    client = client_for(actor, space, native)
    binding = AdapterBinding.objects.get(pk=case["binding_id"])
    now = timezone.now()
    artifact = AdapterArtifact.objects.create(makerspace=space, binding=binding, operation_id=uuid4(),
        kind="thumbnail", content_type="image/jpeg", size_bytes=200, object_key="adapter-artifacts/p1",
        status="ready", expires_at=now + timedelta(days=1))
    point = AdapterTelemetryPoint.objects.create(makerspace=space, binding=binding, series="temp.bed",
        ts=now - timedelta(minutes=1), avg=60, min=60, max=60)
    event = AdapterEvent.objects.create(makerspace=space, device=case["device"], binding=binding,
        operation_id=uuid4(), capability="detection.report", event_type="detection.reported",
        observed_at=now, data={"kind": "smoke"})
    objects = {"binding": binding, "device": case["device"], "machine": case["machine"],
               "artifact": artifact, "point": point, "event": event}
    if kind == "integrations":
        url = reverse("devices:admin-adapter-detail", args=[case["device"].pk])
        call = lambda c: c.get(url)
    elif kind in {"artifacts", "detections", "telemetry_history"}:
        route = {"artifacts": "artifacts", "detections": "detections", "telemetry_history": "telemetry"}[kind]
        url = reverse(f"devices:admin-adapter-{route}", args=[binding.pk])
        call = lambda c: c.get(url)
    elif kind == "diagnostics":
        url = reverse("devices:admin-adapter-log-bundle", args=[binding.pk])
        call = lambda c: c.post(url, {}, format="json")
    else:
        url = reverse("devices:admin-adapter-watch-create", args=[binding.pk])
        body = {"reason": "Retained camera inspection"}
        if kind in {"audio", "talk", "audio_recording"}:
            body["audio"] = True
        if kind == "talk":
            body["talk"] = True
        if kind in {"recording", "audio_recording"}:
            body.update(record=True, notice_ack=True)
        call = lambda c: c.post(url, body, format="json")
    prove_route(space, client, objects, key, call, off=(404, "not_found"),
                on=(201 if kind in {"video", "audio", "talk", "recording", "audio_recording", "diagnostics"} else 200, None),
                check=lambda response: _normal(response, kind, objects), outsiders=staff_outsiders(native))


def _normal(response, kind, objects):
    if kind in {"artifacts", "detections"}:
        row = objects["artifact" if kind == "artifacts" else "event"]
        assert [str(item["id"]) for item in response.data["results"]] == [str(row.pk)]
    elif kind == "telemetry_history":
        assert response.data["series"] == ["temp.bed"]
    elif kind == "integrations":
        assert str(response.data["id"]) == str(objects["device"].pk)
    elif kind == "diagnostics":
        assert response.data["status"] == "queued"
    else:
        assert response.data["audio"] is (kind in {"audio", "talk", "audio_recording"})
        assert response.data["talk"] is (kind == "talk")
        assert response.data["record"] is (kind in {"recording", "audio_recording"})

pytestmark = ([pytestmark] if not isinstance(pytestmark, list) else pytestmark) + [
    pytest.mark.usefixtures("cx11b_isolated_phase")]

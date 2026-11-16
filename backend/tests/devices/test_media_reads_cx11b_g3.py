"""Retained adapter artifacts, detection evidence and telemetry; decision 520 standing."""
import pytest
from tests.modules.test_switch_matrix_objects_rest_isolation import cx11b_isolated_phase  # noqa: F401

from apps.devices.models import AdapterCommand, AdapterTelemetryPoint
from tests.devices.route_world_cx11b_g3 import BASE_KEYS, artifact, event, world
from tests.maintenance.route_support_cx11b_g3 import foreign_refusal, prove, send

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.area_devices, pytest.mark.area_machines]
OPS = {"artifacts": "artifacts", "artifact_url": "artifacts", "detections": "detections",
       "telemetry": "telemetry_history", "bundle": "diagnostics"}
CASES = [(op, key, native) for op, child in OPS.items()
         for key in (*BASE_KEYS, "machines.integrations." + child) for native in (False, True)]


@pytest.mark.parametrize("op,key,native", CASES)
def test_adapter_staff_media_effect_standing_and_switch(op, key, native, monkeypatch):
    w = world(native)
    url = "https://storage.example.test/private-retained"
    monkeypatch.setattr("apps.machines.service_storage.presigned_download_url", lambda *a: url)
    args, method, body, status = [w.binding.pk], "get", {}, 200
    if op in {"artifacts", "artifact_url"}:
        row = artifact(w)
        name = "admin-adapter-artifacts" if op == "artifacts" else "admin-adapter-artifact-url"
        args = [w.binding.pk] if op == "artifacts" else [row.pk]
    elif op == "detections":
        row, name = event(w), "admin-adapter-detections"
    elif op == "telemetry":
        row = AdapterTelemetryPoint.objects.create(makerspace=w.space, binding=w.binding, series="temperature",
            ts=w.now, avg=42.5, min=42, max=43, n=2)
        name, body = "admin-adapter-telemetry", {"series": "temperature", "resolution": 0}
    else:
        name, method, status = "admin-adapter-log-bundle", "post", 201

    def check(response):
        data = response.data
        if op == "artifact_url":
            assert data == {"url": url, "content_type": "image/jpeg", "kind": "thumbnail"}
        elif op == "artifacts":
            assert [(r["id"], r["size_bytes"], r["service_request_id"]) for r in data["results"]] == [
                (str(row.pk), 123, w.job.pk)]
        elif op == "detections":
            assert [(r["id"], r["kind"], r["confidence"], r["note"]) for r in data["results"]] == [
                (str(row.pk), "smoke", 0.75, "Staff only")]
        elif op == "telemetry":
            assert (data["binding_id"], data["series"], data["selected"], data["resolution"]) == (
                str(w.binding.pk), ["temperature"], "temperature", 0)
            assert data["points"] == [{"ts": row.ts, "avg": 42.5, "min": 42, "max": 43, "n": 2}]
        else:
            queued = AdapterCommand.objects.get(pk=data["command_id"])
            assert (queued.binding_id, queued.capability, queued.command, queued.params) == (
                w.binding.pk, "diagnostics", "log_bundle", {"max_bytes": 10485760, "since_seconds": 21600})
            assert AdapterCommand.objects.filter(binding=w.binding).count() == 1
            assert data["status"] == "queued"

    prove(w.space, w.objects, key, lambda c: send(c or w.client, "devices:" + name, args, method, body), check,
          status=status, outsiders=[(w.foreign, foreign_refusal(native))],
          audits={"devices.adapter_command_queued": 1} if op == "bundle" else {})

pytestmark = ([pytestmark] if not isinstance(pytestmark, list) else pytestmark) + [
    pytest.mark.usefixtures("cx11b_isolated_phase")]

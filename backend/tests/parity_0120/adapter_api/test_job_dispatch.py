"""job.dispatch / file.fetch / safety gates: an adapter drives the SAME machine-service workflow as a printer."""
import time
import uuid

import pytest
from django.urls import reverse

from apps.devices.models import AdapterBinding, AdapterCommand, AdapterStatus, DeviceCommand, PrinterJob
from tests.parity_0120.adapter_api.adapter_case import adapter_case
from tests.test_machine_service_workflow import in_progress

pytestmark = pytest.mark.django_db(transaction=True)
CAPS = ("status", "events", "control", "safety", "job.dispatch", "file.fetch")


def dispatched(slug):
    case = adapter_case(slug, caps=CAPS)
    row = in_progress(case["space"], actor=case["manager"], target=case["machine"])
    created = case["client"].post(reverse("devices:admin-adapter-job-create", args=[case["binding_id"]]),
                                  {"service_request_id": row.pk}, format="json")
    assert created.status_code == 201, created.data
    case.update(request=row, job_id=created.data["job_id"])
    return case


def lease_and_ack(case, external="vendor-1"):
    leased = case["sim"].post("jobs/lease")
    assert leased.status_code == 200 and leased.data["job"], leased.data
    job = leased.data["job"]
    acked = case["sim"].post(f"jobs/{job['job_id']}/ack", {"lease_token": job["lease_token"], "external_job_id": external})
    assert acked.status_code == 200, acked.data
    return job


def report(case, job, **changes):
    body = {"operation_id": str(uuid.uuid4()), "outcome": "completed", "actual_minutes": 12, "consumptions": [], **changes}
    return body, case["sim"].post(f"jobs/{job['job_id']}/report", body)


def test_lease_ack_progress_report_goes_through_the_printer_claim_path_into_staff_review():
    case = dispatched("job-flow")
    job = lease_and_ack(case)
    assert case["sim"].post(f"jobs/{job['job_id']}/progress", {"progress_percent": 40}).status_code == 200
    body, response = report(case, job)
    assert response.status_code == 200, response.data
    row = PrinterJob.objects.get(pk=job["job_id"])
    assert row.state == "needs_review" and row.actual_minutes == 12 and row.external_job_id == "vendor-1"
    assert DeviceCommand.objects.get(pk=row.command_id).kind == "adapter_job"


def test_a_terminal_report_is_idempotent_and_a_different_one_conflicts():
    case = dispatched("job-idem")
    job = lease_and_ack(case)
    body, first = report(case, job)
    assert first.status_code == 200
    assert case["sim"].post(f"jobs/{job['job_id']}/report", body).status_code == 200
    changed = case["sim"].post(f"jobs/{job['job_id']}/report", {**body, "actual_minutes": 99})
    assert changed.status_code == 409


def test_a_report_before_the_ack_is_refused_and_files_need_the_live_job():
    case = dispatched("job-order")
    leased = case["sim"].post("jobs/lease").data["job"]
    assert report(case, leased)[1].status_code == 409
    assert case["sim"].get(f"jobs/{leased['job_id']}/file").status_code in (409, 404)


def test_the_generic_printer_lease_never_delivers_an_adapter_job():
    case = dispatched("job-generic")
    from apps.devices.principal import DevicePrincipal
    from apps.devices.services_commands import lease_command
    assert lease_command(DevicePrincipal.from_device(case["device"])) is None


def test_an_unassigned_request_cannot_be_dispatched():
    case = adapter_case("job-unassigned", caps=CAPS)
    response = case["client"].post(reverse("devices:admin-adapter-job-create", args=[case["binding_id"]]),
                                   {"service_request_id": 999999}, format="json")
    assert response.status_code == 400


def test_the_area_clear_gate_holds_the_lease_until_the_area_is_confirmed():
    case = dispatched("job-area")
    configured = case["client"].put(reverse("devices:admin-adapter-binding-config", args=[case["binding_id"]]),
                                    {"require_area_clear": True}, format="json")
    assert configured.status_code == 200, configured.data
    # The confirmation lives on the binding's status row, so the adapter has reported once (as it always does).
    case["sim"].post("status", {"items": [{"binding_id": case["binding_id"], "observed_at": int(time.time()), "state": "idle"}]})
    assert case["sim"].post("jobs/lease").data["job"] is None
    cleared = case["sim"].post("events", {"events": [{
        "operation_id": str(uuid.uuid4()), "binding_id": case["binding_id"], "type": "safety.area_cleared",
        "observed_at": int(time.time()), "data": {"confirmed": True}}]})
    assert cleared.status_code == 200
    assert case["sim"].post("jobs/lease").data["job"] is not None
    # one confirmation covers exactly one job
    assert AdapterStatus.objects.get(binding_id=case["binding_id"]).payload["area_clear"] is False


def test_idle_auto_off_queues_a_power_off_command_server_side():
    from datetime import timedelta
    from django.utils import timezone
    from apps.devices.services_adapter_safety import sweep_safety
    case = adapter_case("job-autooff", caps=CAPS)
    case["client"].put(reverse("devices:admin-adapter-binding-config", args=[case["binding_id"]]),
                       {"auto_off_idle_minutes": 5}, format="json")
    now = int(time.time())
    case["sim"].post("status", {"items": [{"binding_id": case["binding_id"], "observed_at": now - 1200, "state": "idle"}]})
    binding = AdapterBinding.objects.get(pk=case["binding_id"])
    status = binding.status
    status.payload = {**status.payload, "idle_since": now - 1200}
    status.save(update_fields=["payload"])
    counts = sweep_safety(now=timezone.now() + timedelta(seconds=1))
    assert counts["auto_off"] == 1
    command = AdapterCommand.objects.get(binding=binding, capability="control")
    assert command.command == "power" and command.params == {"on": False} and command.created_by_id is None
    assert sweep_safety()["auto_off"] == 0  # cooled down: not queued twice

"""Controls (lease/ack, audit with the staff actor), status idempotency, event idempotency and handlers."""
import time
import uuid

import pytest
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.devices.models import AdapterCommand, AdapterStatus
from apps.machines.models import MachineErrorLog
from tests.parity_0120.adapter_api.adapter_case import adapter_case

pytestmark = pytest.mark.django_db(transaction=True)


def _send(case, command, params=None):
    url = reverse("devices:admin-adapter-binding-command", args=[case["binding_id"]])
    return case["client"].post(url, {"capability": "control", "command": command, "params": params or {}}, format="json")


def test_a_control_command_is_leased_acknowledged_and_audited_with_the_staff_actor():
    case = adapter_case("cmd-flow")
    queued = _send(case, "pause")
    assert queued.status_code == 201, queued.data
    audit = AuditLog.objects.get(action="devices.adapter_command_queued")
    assert audit.actor_id == case["manager"].pk and audit.meta["command"] == "pause"
    leased = case["sim"].post("commands/lease").data["command"]
    assert leased["command"] == "pause" and leased["capability"] == "control"
    assert case["sim"].post("commands/lease").data["command"] is None  # nothing else queued, leased one is hidden
    ack = case["sim"].post(f"commands/{leased['command_id']}/ack",
                           {"lease_token": leased["lease_token"], "outcome": "succeeded"})
    assert ack.status_code == 200 and ack.data["status"] == "succeeded"
    again = case["sim"].post(f"commands/{leased['command_id']}/ack",
                             {"lease_token": leased["lease_token"], "outcome": "succeeded"})
    assert again.status_code == 200  # idempotent re-ack
    assert AuditLog.objects.filter(action="devices.adapter_command_acked", actor__isnull=True).count() == 1


def test_a_wrong_lease_token_is_a_typed_conflict():
    case = adapter_case("cmd-token")
    _send(case, "resume")
    leased = case["sim"].post("commands/lease").data["command"]
    response = case["sim"].post(f"commands/{leased['command_id']}/ack",
                                {"lease_token": "x" * 40, "outcome": "failed"})
    assert response.status_code == 409 and response.data["code"] == "lease_mismatch"


def test_command_params_are_validated_against_the_published_schema():
    case = adapter_case("cmd-schema")
    assert _send(case, "power", {}).status_code == 400  # `on` is required
    assert _send(case, "explode").status_code == 400
    assert _send(case, "power", {"on": False}).status_code == 201


def test_a_capability_the_binding_does_not_serve_is_a_409():
    case = adapter_case("cmd-cap")
    url = reverse("devices:admin-adapter-binding-command", args=[case["binding_id"]])
    response = case["client"].post(url, {"capability": "door.access", "command": "unlock", "params": {"seconds": 3}},
                                   format="json")
    assert response.status_code == 409 and response.data["code"] == "capability_missing"


def test_status_is_stored_then_stale_then_validated():
    case = adapter_case("st-flow")
    now = int(time.time())
    item = {"binding_id": case["binding_id"], "observed_at": now - 30, "state": "running", "progress_percent": 12}
    first = case["sim"].post("status", {"items": [item]})
    assert first.data["results"][0]["result"] == "stored"
    assert AdapterStatus.objects.get(binding_id=case["binding_id"]).state == "running"
    assert case["sim"].post("status", {"items": [item]}).data["results"][0]["result"] == "stale"
    bad = case["sim"].post("status", {"items": [{**item, "observed_at": now - 10, "state": "printing"}]})
    assert bad.status_code == 400 and bad.data["code"] == "invalid_payload"
    ghost = case["sim"].post("status", {"items": [{**item, "binding_id": str(uuid.uuid4())}]})
    assert ghost.data["results"][0]["result"] == "unknown_binding"


def test_events_are_idempotent_by_operation_id_and_a_fault_reaches_the_maintenance_log():
    case = adapter_case("ev-fault")
    event = {"operation_id": str(uuid.uuid4()), "binding_id": case["binding_id"], "type": "maintenance.fault",
             "observed_at": int(time.time()), "data": {"code": "hotend_clog", "severity": "fault", "detail": "clog"}}
    first = case["sim"].post("events", {"events": [event]})
    second = case["sim"].post("events", {"events": [event]})
    assert first.data["results"][0]["result"] == "stored" and second.data["results"][0]["result"] == "duplicate"
    assert MachineErrorLog.objects.filter(machine=case["machine"], message__contains="hotend_clog").count() == 1


def test_an_event_for_another_adapters_binding_is_a_404():
    mine, other = adapter_case("ev-own-a"), adapter_case("ev-own-b")
    event = {"operation_id": str(uuid.uuid4()), "binding_id": other["binding_id"], "type": "maintenance.fault",
             "observed_at": int(time.time()), "data": {"code": "x1", "severity": "info"}}
    assert mine["sim"].post("events", {"events": [event]}).status_code == 404


def test_unbinding_expires_queued_commands():
    case = adapter_case("cmd-unbind")
    _send(case, "pause")
    assert case["client"].delete(reverse("devices:admin-adapter-binding-detail", args=[case["binding_id"]])).status_code == 204
    assert not AdapterCommand.objects.filter(status="queued").exists()

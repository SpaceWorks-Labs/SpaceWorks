"""SECFIX-A F2: command TTL and lease bounds (lead 4), cross-tenant enqueue (L-A6), detection run window (lead 5/L-A1)."""
import time
import uuid
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.devices.models import AdapterCommand
from apps.machines.models import MachineServiceRequest
from tests.parity_0120.adapter_api.adapter_case import adapter_case, plain_member
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db(transaction=True)
DETECT = ("status", "events", "artifact.upload", "detection.report")


def _send(case, command="pause", binding_id=None):
    url = reverse("devices:admin-adapter-binding-command", args=[binding_id or case["binding_id"]])
    return case["client"].post(url, {"capability": "control", "command": command, "params": {}}, format="json")


def _ack(case, leased, outcome="succeeded"):
    return case["sim"].post(f"commands/{leased['command_id']}/ack",
                            {"lease_token": leased["lease_token"], "outcome": outcome})


def _past(seconds=5):
    return timezone.now() - timedelta(seconds=seconds)


# --- lead 4: expired commands -----------------------------------------------------------------------------------
def test_a_command_whose_ttl_passed_while_leased_is_never_leased_again():
    case = adapter_case("f2-cmd-expired")
    assert _send(case).status_code == 201
    leased = case["sim"].post("commands/lease").data["command"]
    AdapterCommand.objects.filter(pk=leased["command_id"]).update(expires_at=_past(), lease_expires_at=_past())
    assert case["sim"].post("commands/lease").data["command"] is None  # the attack: it used to come back out
    row = AdapterCommand.objects.get(pk=leased["command_id"])
    assert row.status == "expired" and row.lease_token_digest is None


def test_a_lapsed_lease_inside_the_ttl_is_requeued_and_delivered_again():
    case = adapter_case("f2-cmd-requeue")
    _send(case)
    first = case["sim"].post("commands/lease").data["command"]
    AdapterCommand.objects.filter(pk=first["command_id"]).update(lease_expires_at=_past())
    again = case["sim"].post("commands/lease").data["command"]
    assert again["command_id"] == first["command_id"] and again["lease_token"] != first["lease_token"]
    assert AdapterCommand.objects.get(pk=first["command_id"]).attempts == 2
    assert _ack(case, again).status_code == 200  # the normal path still completes


def test_a_lease_never_outlives_the_command(settings):
    settings.DEVICE_COMMAND_LEASE_SECONDS = 7200  # longer than the ten-minute command TTL
    case = adapter_case("f2-cmd-cap")
    _send(case)
    leased = case["sim"].post("commands/lease").data["command"]
    row = AdapterCommand.objects.get(pk=leased["command_id"])
    assert row.lease_expires_at == row.expires_at
    assert leased["lease_expires_at"] == int(row.expires_at.timestamp())


def test_an_ack_after_the_ttl_is_refused_closed_and_audited():
    case = adapter_case("f2-cmd-late")
    _send(case)
    leased = case["sim"].post("commands/lease").data["command"]
    AdapterCommand.objects.filter(pk=leased["command_id"]).update(expires_at=_past(), lease_expires_at=_past())
    late = _ack(case, leased)
    assert late.status_code == 410 and late.data["code"] == "lease_expired"
    row = AdapterCommand.objects.get(pk=leased["command_id"])
    assert row.status == "expired" and row.result_code == "command_expired"
    refused = AuditLog.objects.get(action="devices.adapter_command_ack_refused")
    assert refused.meta["reason"] == "command_expired" and refused.meta["reported_outcome"] == "succeeded"
    assert not AuditLog.objects.filter(action="devices.adapter_command_acked").exists()


def test_an_ack_after_the_lease_lapsed_is_refused_and_the_command_requeued():
    case = adapter_case("f2-cmd-lapsed")
    _send(case)
    leased = case["sim"].post("commands/lease").data["command"]
    AdapterCommand.objects.filter(pk=leased["command_id"]).update(lease_expires_at=_past())
    late = _ack(case, leased, "failed")
    assert late.status_code == 410 and late.data["code"] == "lease_expired"
    assert AdapterCommand.objects.get(pk=leased["command_id"]).status == "queued"


def test_an_ack_in_time_still_succeeds():
    case = adapter_case("f2-cmd-ok")
    _send(case)
    leased = case["sim"].post("commands/lease").data["command"]
    ok = _ack(case, leased)
    assert ok.status_code == 200 and ok.data["status"] == "succeeded"


def test_late_reasons_cover_a_rotated_key_before_time():
    from apps.devices.services_adapter_commands import _late
    now = timezone.now()
    future = now + timedelta(minutes=5)
    live = SimpleNamespace(device_key_version=1, expires_at=future, lease_expires_at=future)
    assert _late(live, SimpleNamespace(key_version=1), now) == ""
    assert _late(live, SimpleNamespace(key_version=2), now) == "key_rotated"
    expired = SimpleNamespace(device_key_version=1, expires_at=now, lease_expires_at=future)
    assert _late(expired, SimpleNamespace(key_version=1), now) == "command_expired"
    lapsed = SimpleNamespace(device_key_version=1, expires_at=future, lease_expires_at=now)
    assert _late(lapsed, SimpleNamespace(key_version=1), now) == "lease_lapsed"


# --- L-A6: another tenant's binding is the same 404 as a missing one --------------------------------------------
def test_enqueue_to_another_tenants_binding_is_an_indistinguishable_404():
    mine, theirs = adapter_case("f2-cmd-tenant-a"), adapter_case("f2-cmd-tenant-b")
    foreign = _send(mine, binding_id=theirs["binding_id"])
    missing = _send(mine, binding_id=str(uuid.uuid4()))
    assert foreign.status_code == missing.status_code == 404
    assert not AdapterCommand.objects.filter(binding_id=theirs["binding_id"]).exists()
    assert _send(mine).status_code == 201  # own binding still works


# --- lead 5 / L-A1: a job owner sees detections from their own run only -----------------------------------------
def _detect(case, observed_at):
    event = {"operation_id": str(uuid.uuid4()), "binding_id": case["binding_id"], "type": "detection.reported",
             "observed_at": int(observed_at), "data": {"kind": "failure", "confidence": 0.9}}
    response = case["sim"].post("events", {"events": [event]})
    assert response.status_code == 200, response.data


def test_a_former_job_owner_cannot_read_later_jobs_detections():
    from tests.test_machine_service_workflow import in_progress
    case = adapter_case("f2-detect-window", caps=DETECT)
    row = in_progress(case["space"], actor=case["manager"], target=case["machine"])
    now = time.time()
    started, finished = timezone.now() - timedelta(seconds=600), timezone.now() - timedelta(seconds=300)
    MachineServiceRequest.objects.filter(pk=row.pk).update(started_at=started, completed_at=finished,
                                                           status="completed")
    _detect(case, now - 700)  # before the run: another job
    _detect(case, now - 450)  # during the run: theirs
    _detect(case, now - 100)  # after the run ended: a later member's job
    owner = authenticated_client(row.member or row.requester)
    seen = owner.get(f"/api/v1/member/adapter-detections/requests/{row.pk}")
    assert seen.status_code == 200 and seen.data["count"] == 1


def test_a_running_job_owner_sees_detections_since_it_started():
    from tests.test_machine_service_workflow import in_progress
    case = adapter_case("f2-detect-running", caps=DETECT)
    row = in_progress(case["space"], actor=case["manager"], target=case["machine"])
    _detect(case, time.time())
    owner = authenticated_client(row.member or row.requester)
    assert owner.get(f"/api/v1/member/adapter-detections/requests/{row.pk}").data["count"] == 1
    stranger = authenticated_client(plain_member("f2-detect-stranger", case["space"]))
    assert stranger.get(f"/api/v1/member/adapter-detections/requests/{row.pk}").status_code == 404


def test_a_job_that_never_started_has_no_detection_window():
    from apps.devices.services_adapter_detect import run_window
    assert run_window(SimpleNamespace(started_at=None, completed_at=None, failed_at=None, cancelled_at=None)) is None
    started = timezone.now().replace(microsecond=500)
    ended = started + timedelta(minutes=5)
    window = run_window(SimpleNamespace(started_at=started, completed_at=None, failed_at=ended, cancelled_at=None))
    assert window == (started.replace(microsecond=0), ended.replace(microsecond=0) + timedelta(seconds=1))

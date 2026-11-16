"""ETA surfaces agree on one frozen snapshot, stay PII-free and stay within the query budget."""

from uuid import uuid4

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.rbac import Action
from apps.audit.models import AuditLog
from apps.integrations.models_contract import NotificationEnvelope
from apps.machines import service_queue_eta
from apps.machines.models import Machine, MachineServiceRequest, MachineType, ServiceQueue
from apps.machines.public_detail import queue_summaries
from apps.machines.service_queue_eta import machine_queue_summaries_for, queue_snapshot_for
from apps.makerspaces.member_activity_service import active_membership, member_activity
from tests.account_split.sweep_helpers import configured_membership, make_role_account
from tests.account_split_g2_helpers import staff_for_actions
from tests.machines.eta_helpers import NOW, approved, at, enable, job, owner, owner_fixture, pending, world
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db

STATUS_KEYS = {
    "public_token", "status", "title", "machine_type_name", "created_at", "accepted_at", "started_at",
    "completed_at", "cancelled_at", "estimated_minutes", "queue_position", "queue_approved_ahead",
    "queue_awaiting_review_ahead", "eta",
}
ETA_KEYS = {
    "calculated_at", "estimated_start_at", "estimated_finish_at", "start_in_minutes", "finish_in_minutes",
    "confidence", "reasons", "approved_ahead", "awaiting_review_ahead", "active_machine_count",
    "missing_estimate_count",
}


@pytest.fixture
def frozen(monkeypatch):
    monkeypatch.setattr(service_queue_eta, "_now", lambda: NOW)
    return NOW


def status_url(row):
    return f"/api/v1/public/machine-service/requests/{row.public_token}/status"


def member_world(slug, **kwargs):
    w = world(slug, membership=True, **kwargs)
    member = make_role_account(w.space, role_slug="member", username=f"{slug}-member-{uuid4().hex[:6]}",
                               email=f"{slug}@example.test", access_status="active")
    configured_membership(user=member, makerspace=w.space)
    return w, member


def test_one_snapshot_agrees_across_status_member_staff_and_summaries(frozen):
    w, member = member_world("eta-agree")
    case = owner_fixture(w)
    MachineServiceRequest.objects.filter(pk=case.target.pk).update(member=member, requester=member)
    case.target.refresh_from_db()
    expected = queue_snapshot_for([case.target], now=NOW).eta(case.target)
    assert (expected["start_in_minutes"], expected["finish_in_minutes"]) == (50, 65)
    public = APIClient().get(status_url(case.target)).json()
    assert public["eta"]["estimated_start_at"].startswith("2026-10-18T10:50")
    assert public["eta"]["estimated_finish_at"].startswith("2026-10-18T11:05")
    activity = member_activity(active_membership(member, w.space.pk))
    row = next(item for item in activity["machine_service_requests"] if item["request_id"] == case.target.pk)
    assert row["eta"]["start_in_minutes"] == 50 and row["can_cancel"] is True and row["queue_position"] == 3
    staff = authenticated_client(w.staff).get(
        f"/api/v1/admin/makerspaces/{w.space.pk}/machine-service/requests?machine_type_id={w.kind.pk}").json()
    staff_row = next(item for item in staff if item["id"] == case.target.pk)
    assert staff_row["eta"]["finish_in_minutes"] == 65
    summaries = machine_queue_summaries_for(w.machines, now=NOW)
    assert summaries[w.machines[0].pk]["eta_minutes"] == 70 and summaries[w.machines[1].pk]["eta_minutes"] == 65
    machines = authenticated_client(w.staff).get(f"/api/v1/admin/makerspace/{w.space.pk}/machines").json()["results"]
    assert {item["id"]: item["service_queue_summary"]["eta_minutes"] for item in machines} == {
        w.machines[0].pk: 70, w.machines[1].pk: 65}
    for machine in w.machines:
        machine.public_fields = ["queue_eta"]
        machine.save(update_fields=["public_fields"])
    public_summaries = queue_summaries(list(Machine.objects.select_related("makerspace").filter(makerspace=w.space)))
    assert public_summaries[w.machines[1].pk]["eta_minutes"] == 65


def test_public_status_is_an_explicit_pii_free_allowlist_counting_private_capacity(frozen):
    w = world("eta-privacy")
    Machine.objects.filter(pk=w.machines[1].pk).update(is_public=False)
    other = approved(w, 30, created=-10, title="Someone else's secret")
    target = approved(w, 15, created=-5, title="Mine")
    body = APIClient().get(status_url(target)).json()
    assert set(body) == STATUS_KEYS and set(body["eta"]) == ETA_KEYS
    flat = str(body)
    for leaked in (other.title, str(other.public_token), other.requester.email, other.requester.username):
        assert leaked not in flat
    assert body["eta"]["active_machine_count"] == 2 and body["eta"]["start_in_minutes"] == 0
    assert body["status"] == "accepted" and body["machine_type_name"] == "Laser cutter"


def test_token_and_tenant_policy_is_preserved(frozen):
    w = world("eta-policy")
    row = job(w)
    assert APIClient().get(f"/api/v1/public/machine-service/requests/{uuid4()}/status").status_code == 404
    enable(w.space, off=("machine_service",))
    # A module that is off answers a typed 404, never a 400 (c4f6064e, #183B gap 12).
    assert APIClient().get(status_url(row)).status_code == 404
    enable(w.space)
    w.space.archived_at = timezone.now()
    w.space.save(update_fields=["archived_at"])
    assert APIClient().get(status_url(row)).status_code == 404


def test_local_type_sharing_the_printer_slug_is_generic_and_separate(frozen):
    w = world("eta-slug")
    local = MachineType.objects.create(makerspace=w.space, slug="3d_printer", name="Local printer-ish")
    Machine.objects.create(makerspace=w.space, machine_type=local, name="Local")
    queue = ServiceQueue.objects.create(makerspace=w.space, machine_type=local, name="Local queue")
    row = job(w, target=queue)
    approved(w, 600, created=-1)  # laser work must not delay the local-type job
    assert APIClient().get(f"/api/v1/public/machine-service/3d-printer/requests/{row.public_token}/status").status_code == 404
    body = APIClient().get(status_url(row)).json()
    assert body["eta"]["active_machine_count"] == 1 and body["machine_type_name"] == "Local printer-ish"


def test_printer_status_route_carries_the_same_eta(frozen):
    w = world("eta-printer", printing=True)
    member = owner("eta-printer")
    # Built-in printer intake needs a material catalogue; the ETA only needs the rows.
    common = {"makerspace": w.space, "queue": w.queue, "requester": member, "member": member}
    for machine, minutes in zip(w.machines, (20, 40)):
        MachineServiceRequest.objects.create(**common, title="Running", status="in_progress", assigned_machine=machine,
                                             started_at=at(-10), estimated_minutes=minutes, run_estimated_minutes=minutes)
        Machine.objects.filter(pk=machine.pk).update(status=Machine.Status.RUNNING)
    rows = [MachineServiceRequest.objects.create(**common, title=f"Job {i}", status="accepted", estimated_minutes=minutes)
            for i, minutes in enumerate((60, 20, 15))]
    for offset, row in zip((-50, -40, -30), rows):
        MachineServiceRequest.objects.filter(pk=row.pk).update(created_at=at(offset))
    body = APIClient().get(f"/api/v1/public/machine-service/3d-printer/requests/{rows[2].public_token}/status").json()
    assert body["eta"]["start_in_minutes"] == 50 and body["eta"]["finish_in_minutes"] == 65
    assert body["queue_position"] == 3 and body["queue_approved_ahead"] == body["eta"]["approved_ahead"] == 2
    generic = APIClient().get(status_url(rows[2])).json()
    assert generic["eta"] == body["eta"]


def test_member_ownership_is_member_id_never_the_requester_fk(frozen):
    w, member = member_world("eta-owner")
    stranger = make_role_account(w.space, role_slug="member", username=f"eta-stranger-{uuid4().hex[:6]}",
                                 email="stranger@example.test", access_status="active")
    mine = job(w, "Mine", member=member)
    theirs = job(w, "Theirs", member=stranger)
    MachineServiceRequest.objects.filter(pk=theirs.pk).update(requester=member)
    activity = member_activity(active_membership(member, w.space.pk))
    assert [row["request_id"] for row in activity["machine_service_requests"]] == [mine.pk]


def test_collect_only_staff_get_no_live_queue_or_summaries(frozen):
    w = world("eta-collect")
    approved(w, 30, created=-3)
    done = approved(w, 10, created=-2, title="Done")
    from apps.machines import role_scope
    from apps.machines.service_workflow import complete, start
    start(done, w.staff, role_scope.EXEMPT, machine_id=w.machines[1].pk)
    complete(done, w.staff, actual_minutes=10, consumptions=[])
    collector, _ = staff_for_actions(w.space, f"eta-collector-{uuid4().hex[:6]}", [Action.COLLECT_SERVICE_REQUEST])
    rows = authenticated_client(collector).get(f"/api/v1/admin/makerspaces/{w.space.pk}/machine-service/requests").json()
    assert [row["status"] for row in rows] == ["completed"] and rows[0]["eta"] is None


def test_reads_never_write_markers_envelopes_audit_or_rows(frozen):
    w, member = member_world("eta-reads")
    case = owner_fixture(w)
    before = (NotificationEnvelope.objects.count(), AuditLog.objects.count(),
              list(MachineServiceRequest.objects.order_by("pk").values_list("updated_at", "started_notice_at")))
    APIClient().get(status_url(case.target))
    member_activity(active_membership(member, w.space.pk))
    authenticated_client(w.staff).get(f"/api/v1/admin/makerspaces/{w.space.pk}/machine-service/requests")
    machine_queue_summaries_for(w.machines, now=NOW)
    after = (NotificationEnvelope.objects.count(), AuditLog.objects.count(),
             list(MachineServiceRequest.objects.order_by("pk").values_list("updated_at", "started_notice_at")))
    assert before == after


def test_estimator_queries_are_bounded_regardless_of_targets_scopes_and_machines(frozen):
    w = world("eta-budget", machines=6)
    extra = ServiceQueue.objects.create(makerspace=w.space, machine_type=w.kind, name="Second queue")
    rows = [approved(w, 5, created=-i, target=w.queue if i % 2 else extra) for i in range(50)]
    rows += [pending(w, 5, created=-60)]
    for count in (1, 51):
        targets = list(MachineServiceRequest.objects.filter(pk__in=[row.pk for row in rows[:count]]))
        with CaptureQueriesContext(connection) as captured:
            snapshot = queue_snapshot_for(targets, machines=w.machines, now=NOW)
            [snapshot.eta(row) for row in targets]
            [snapshot.machine_summary(machine) for machine in w.machines]
        assert len(captured.captured_queries) <= 4, count
    assert at(0) == NOW

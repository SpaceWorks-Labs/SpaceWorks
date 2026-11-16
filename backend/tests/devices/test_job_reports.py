"""Queue pull and job reports map onto the machine-service workflow (release 2 L10)."""
import uuid

import pytest

from apps.audit.models import AuditLog
from apps.devices.models import PrinterJob
from apps.devices.services_printer_apply import approve_report
from tests.devices.sim_agent import accepted_request, integrated_case, started_request

pytestmark = pytest.mark.django_db(transaction=True)


def _terminal(event="completed", **changes):
    body = {"event": event, "external_job_id": "run-1", "operation_id": str(uuid.uuid4()),
            "actual_minutes": 12, "consumptions": []}
    if event == "failed":
        body.update(failure_reason="Spaghetti", percent_complete=30)
    return {**body, **changes}


def test_the_queue_lists_approved_jobs_of_the_type_and_this_machines_running_job():
    case = integrated_case("rep-queue")
    waiting, running = accepted_request(case), started_request(case)
    data = case["agent"].queue().data
    assert data["machine_id"] == case["machine"].pk and data["integration_kind"] == "printer_agent"
    by_id = {job["service_request_id"]: job for job in data["jobs"]}
    assert by_id[waiting.pk]["status"] == "accepted" and by_id[running.pk]["on_this_machine"] is True
    assert set(by_id[running.pk]) == {"service_request_id", "status", "on_this_machine", "estimated_minutes",
                                      "planned_grams", "accepted_at", "started_at", "printer_job_id"}


def test_started_attaches_once_and_a_different_run_conflicts():
    case = integrated_case("rep-start")
    row = started_request(case)
    first = case["agent"].report(row.pk, event="started", external_job_id="run-1")
    assert first.status_code == 200 and first.data["state"] == "awaiting"
    again = case["agent"].report(row.pk, event="started", external_job_id="run-1")
    assert again.data["id"] == first.data["id"] and PrinterJob.objects.count() == 1
    other = case["agent"].report(row.pk, event="started", external_job_id="run-2")
    assert other.status_code == 409 and other.data["code"] == "job_conflict"
    assert case["agent"].queue().data["jobs"][0]["printer_job_id"] == first.data["id"]


def test_a_job_staff_have_not_started_is_refused_and_audited():
    case = integrated_case("rep-not-started")
    row = accepted_request(case)
    response = case["agent"].report(row.pk, event="started", external_job_id="run-1")
    assert response.status_code == 409 and response.data["code"] == "job_not_started"
    refused = AuditLog.objects.get(action="machine_service.agent_report_refused")
    assert refused.meta["code"] == "job_not_started" and refused.actor_id is None
    row.refresh_from_db()
    assert row.status == "accepted"


def test_completion_is_held_for_review_by_default_then_staff_apply_through_the_workflow():
    case = integrated_case("rep-complete")
    row = started_request(case)
    case["agent"].report(row.pk, event="started", external_job_id="run-1")
    body = _terminal()
    held = case["agent"].report(row.pk, **body)
    assert held.status_code == 200 and held.data["state"] == "needs_review"
    assert case["agent"].report(row.pk, **body).data["state"] == "needs_review"  # repeat is a no-op
    row.refresh_from_db()
    assert row.status == "in_progress"
    assert approve_report(case["actor"], held.data["id"]).state == "applied"
    row.refresh_from_db()
    assert (row.status, row.actual_minutes) == ("completed", 12)
    assert AuditLog.objects.filter(action="machine_service.completed", target_id=str(row.pk)).count() == 1
    changed = case["agent"].report(row.pk, **{**body, "actual_minutes": 99})
    assert changed.status_code == 409


def test_auto_apply_completes_but_a_failure_is_always_held_for_staff():
    case = integrated_case("rep-auto", auto=True)
    done, broken = started_request(case), None
    case["agent"].report(done.pk, event="started", external_job_id="run-1")
    assert case["agent"].report(done.pk, **_terminal()).data["state"] == "applied"
    done.refresh_from_db()
    assert done.status == "completed"
    broken = started_request(case)
    case["agent"].report(broken.pk, event="started", external_job_id="run-9")
    failed = case["agent"].report(broken.pk, **_terminal("failed", external_job_id="run-9"))
    assert failed.status_code == 200 and failed.data["state"] == "needs_review"
    broken.refresh_from_db()
    assert broken.status == "in_progress"
    assert approve_report(case["actor"], failed.data["id"]).state == "applied"
    broken.refresh_from_db()
    assert (broken.status, broken.fail_percent_complete) == ("failed", 30)
    applied = AuditLog.objects.filter(action="machine_service.agent_report_applied").values_list("meta", flat=True)
    assert {meta["event"] for meta in applied} == {"started", "completed", "failed"}


def test_terminal_reports_need_a_started_run_and_a_complete_body():
    case = integrated_case("rep-terminal")
    row = started_request(case)
    assert case["agent"].report(row.pk, **_terminal()).data["code"] == "job_not_reported_started"
    assert case["agent"].report(row.pk, event="completed", external_job_id="run-1").status_code == 400
    assert case["agent"].report(row.pk, event="started", external_job_id="run-1", actual_minutes=3).status_code == 400
    assert case["agent"].report(row.pk, **_terminal(amount="5.00")).status_code == 400


def test_measured_material_goes_through_the_cost_seam(monkeypatch):
    calls = []
    import apps.machines.consumable_costs as costs
    real = costs.record_service_cost
    monkeypatch.setattr(costs, "record_service_cost", lambda request, actor: calls.append(request.pk) or real(request, actor))
    case = integrated_case("rep-cost", auto=True)
    row = started_request(case)
    case["agent"].report(row.pk, event="started", external_job_id="run-1")
    case["agent"].report(row.pk, **_terminal())
    assert calls == [row.pk]

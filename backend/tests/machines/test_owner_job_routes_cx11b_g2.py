"""Owner quote/resubmit/history: exact transition/audit and 520 owner concealment."""
import pytest

from apps.machines import service_workflow_review as review
from apps.machines.models import MachineServiceRequest
from apps.payments.models import Payment
from tests.machines.eta_helpers import job
from tests.machines.member_support_cx11b_g2 import member_world
from tests.machines.route_support_cx11b_g2 import command, prove
from tests.machines.test_job_flow import priced

pytestmark = [pytest.mark.django_db, pytest.mark.area_machines]
CASES = [("member-machine-jobs", "get"), ("member-machine-job-detail", "get"),
         ("member-machine-job-approve-quote", "post"), ("member-machine-job-decline-quote", "post"),
         ("member-machine-job-resubmit", "post"), ("member-machine-service-cancel", "post"),
         ("member-machine-service-owner", "get")]


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("name,method", CASES)
def test_owner_job_real_effect_and_service_switch(native, name, method):
    w = priced(member_world(native))
    row = job(w, member=w.member, title="Retained owner job")
    body = {}
    if name.endswith(("approve-quote", "decline-quote")):
        row = review.send_quote(row, w.actor, estimated_minutes=30)
        body = {"digest": row.quote_digest} if name.endswith("approve-quote") else {}
    if name.endswith("resubmit"):
        row = review.request_changes(row, w.actor, code="wrong_format", message="Please revise")
        body = {"note": "Revised drawing"}
    if name.endswith("cancel"):
        body = {"reason": "No longer needed"}
    args = [] if name == "member-machine-jobs" else [row.public_token if name.endswith("owner") else row.pk]
    def call(c):
        query = {"makerspace": c._credentials.get("HTTP_X_MAKERSPACE_ID", w.space.pk)} if name == "member-machine-jobs" else body
        return command(c, name, method, args, query)

    payments = Payment.objects.count()
    initial = row.status
    event = {"member-machine-job-approve-quote": "quote_approved", "member-machine-job-decline-quote": "quote_declined",
             "member-machine-job-resubmit": "resubmitted", "member-machine-service-cancel": "cancelled"}.get(name)
    status = {"quote_approved": "accepted", "quote_declined": "cancelled", "resubmitted": "pending",
              "cancelled": "cancelled"}.get(event, initial)

    def check(response):
        saved = MachineServiceRequest.objects.get(pk=row.pk)
        assert (saved.status, saved.member_id, saved.title) == (status, w.member.pk, "Retained owner job")
        assert Payment.objects.count() == payments
        if event == "quote_approved":
            assert saved.quote_approved_at is not None
            assert saved.quote_digest == row.quote_digest
        elif event == "resubmitted":
            assert saved.member_note == "Revised drawing"
        elif event in {"quote_declined", "cancelled"}:
            assert saved.cancelled_at is not None
        if name.endswith("owner"):
            assert response.data == {"request_id": row.pk, "can_cancel": True}
        elif name.endswith("cancel"):
            assert (str(response.data["public_token"]), response.data["status"], saved.reason) == (
                str(row.public_token), "cancelled", "No longer needed")
        else:
            data = response.data if name == "member-machine-jobs" else [response.data]
            assert [(r["id"], r["title"], r["status"]) for r in data] == [
                (row.pk, "Retained owner job", status)]

    def history_off(response):
        data = response.data if name == "member-machine-jobs" else [response.data]
        if name.endswith("owner"):
            assert response.data == {"request_id": row.pk, "can_cancel": False}
        else:
            assert [(r["id"], r["title"], r["can_cancel"]) for r in data] == [(row.pk, "Retained owner job", False)]

    read = method == "get"
    for foreign in (w.foreign, w.same_space):
        # Personal list serves the caller's rows; addressed objects conceal their owner (520).
        previous = w.foreign
        w.foreign = foreign
        # Each independent proof runs in a savepoint so both callers see the same original job.
        from tests.modules.test_switch_matrix_objects_rest_isolation import rolled_back
        with rolled_back():
            prove(w, "machine_service", call, check,
                  audits=(f"machine_service.{event}",) if event else (),
                  off=(200, None) if read else (404, "module_disabled"), off_check=history_off if read else None,
                  foreign=(200, None) if name == "member-machine-jobs" else (404, "not_found"),
                  foreign_check=(lambda r: _empty(r)) if name == "member-machine-jobs" else None)
        w.foreign = previous


def _empty(response):
    assert response.data == []


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key,code", [("machines.job_requests", "feature_disabled"),
                                    ("membership", "machine_intake_unavailable"),
                                    ("presence", "machine_intake_unavailable")])
def test_resubmit_rechecks_each_public_intake_dependency(native, key, code):
    w = member_world(native)
    row = review.request_changes(job(w, member=w.member), w.actor, code="other", message="Revise")

    def check(response):
        saved = MachineServiceRequest.objects.get(pk=row.pk)
        assert (saved.status, saved.member_note, response.data["id"]) == ("pending", "Revised", row.pk)

    prove(w, key, lambda c: command(c, "member-machine-job-resubmit", "post", [row.pk], {"note": "Revised"}),
          check, audits=("machine_service.resubmitted",), off=(404, code))

"""CX11B: policy and worker switches change behaviour, not invented URL availability."""
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.machines import job_policy, role_scope, service_workflow as workflow, service_workflow_review as review
from apps.machines.job_rules import JobRuleRefused
from apps.machines.job_sweeps import run_job_flow_sweep
from apps.machines.models import MakerspaceMachineTypePolicy, MachineServiceRequest
from apps.machines.sessions_sweep import run_session_sweep
from tests.machines.eta_helpers import job, world
from tests.machines.session_helpers import open_session, session_world
from tests.machines.test_job_flow import priced
from tests.modules.test_switch_matrix_objects_rest_isolation import rolled_back
from tests.modules.test_switch_matrix_objects_rest_support import _no_write, domain_rows, switch

pytestmark = pytest.mark.django_db


def test_quote_policy_off_allows_acceptance_on_requires_quote_and_retains_job():
    w = priced(world("cx11b-quote-policy"))
    w.space.enabled_features = sorted(set(w.space.enabled_features) | {
        "machines.job_requests", "machines.job_quotes", "charges.enabled", "charges.machines"})
    w.space.save(update_fields=["enabled_features"])
    row = job(w)
    before = domain_rows()
    with pytest.raises(JobRuleRefused) as refused:
        workflow.accept(row, w.staff, estimated_minutes=10)
    assert (refused.value.status_code, refused.value.detail["code"]) == (409, "quote_required")
    assert domain_rows() == before
    original = switch(w.space, job_policy.JOB_QUOTES)
    with rolled_back():
        accepted = workflow.accept(row, w.staff, estimated_minutes=10)
        assert accepted.status == "accepted"
        assert AuditLog.objects.filter(target_id=str(row.pk), action="machine_service.accepted").count() == 1
    assert domain_rows() == before
    switch(w.space, job_policy.JOB_QUOTES, original=original)
    with pytest.raises(JobRuleRefused) as restored:
        workflow.accept(row, w.staff, estimated_minutes=10)
    assert (restored.value.status_code, restored.value.detail["code"]) == (409, "quote_required")
    assert domain_rows() == before


@pytest.mark.parametrize("key", ["machine_service", "machines.job_requests"])
def test_quote_expiry_worker_is_inert_off_and_resumes_once_on(key):
    w = priced(world("cx11b-quote-expiry"))
    w.space.enabled_features = sorted(set(w.space.enabled_features) | {
        "machines.job_requests", "machines.job_quotes", "charges.enabled", "charges.machines"})
    w.space.save(update_fields=["enabled_features"])
    row = review.send_quote(job(w), w.staff, estimated_minutes=10)
    MachineServiceRequest.objects.filter(pk=row.pk).update(quote_expires_at=timezone.now() - timedelta(seconds=1))
    before = domain_rows()
    original = switch(w.space, key)
    with connection.execute_wrapper(_no_write):
        assert run_job_flow_sweep() == {"skipped": 0}
    assert domain_rows() == before
    switch(w.space, key, original=original)
    assert run_job_flow_sweep() == {"skipped": 0, "quote_expired": 1}
    row.refresh_from_db()
    assert row.status == "cancelled"
    assert AuditLog.objects.filter(action="machine_service.quote_expired", target_id=str(row.pk)).count() == 1
    after = domain_rows()
    assert run_job_flow_sweep() == {"skipped": 0}
    assert domain_rows() == after


def test_pay_before_pickup_off_allows_handover_on_requires_settlement_without_erasing_debt():
    from apps.payments.models import Payment
    w = priced(world("cx11b-pickup-policy"))
    w.space.enabled_features = sorted(set(w.space.enabled_features) | {
        "machines.job_requests", "machines.job_quotes", "machines.pay_before_pickup", "charges.enabled", "charges.machines"})
    w.space.save(update_fields=["enabled_features"])
    row = review.send_quote(job(w), w.staff, estimated_minutes=10)
    row = review.approve_quote(row, row.member, digest=row.quote_digest)
    row = workflow.start(row, w.staff, role_scope.EXEMPT, machine_id=w.machines[0].pk)
    row = workflow.complete(row, w.staff, actual_minutes=10, consumptions=[])
    charge = Payment.objects.get(subject_type="machine_service_request", subject_id=row.pk)
    assert (charge.status, charge.provider) == ("pending", "unclaimed")
    before = domain_rows()
    with pytest.raises(JobRuleRefused) as refused:
        workflow.collect(row, w.staff)
    assert (refused.value.status_code, refused.value.detail["code"]) == (409, "payment_due")
    assert domain_rows() == before
    original = switch(w.space, job_policy.PAY_BEFORE_PICKUP)
    with rolled_back():
        assert workflow.collect(row, w.staff).status == "collected"
        charge.refresh_from_db()
        assert (charge.status, charge.provider) == ("pending", "unclaimed")
    switch(w.space, job_policy.PAY_BEFORE_PICKUP, original=original)
    assert domain_rows() == before
    with pytest.raises(JobRuleRefused) as restored:
        workflow.collect(row, w.staff)
    assert (restored.value.status_code, restored.value.detail["code"]) == (409, "payment_due")


@pytest.mark.parametrize("key", ["machines", "machines.sessions"])
def test_session_auto_stop_worker_keeps_live_rows_off_then_stops_exactly_once(key):
    w = session_world("cx11b-session-worker", billing=False)
    MakerspaceMachineTypePolicy.objects.create(makerspace=w.space, machine_type=w.kind, session_max_minutes=60)
    row = open_session(w, minutes_ago=150)
    before = domain_rows()
    original = switch(w.space, key)
    with connection.execute_wrapper(_no_write):
        assert run_session_sweep() == {"skipped": 0, "auto_stopped": 0, "access_expiring_notices": 0}
    assert domain_rows() == before
    switch(w.space, key, original=original)
    assert run_session_sweep() == {"skipped": 0, "auto_stopped": 1, "access_expiring_notices": 0}
    row.refresh_from_db()
    assert (row.stop_reason, row.duration_minutes, row.flagged) == ("max_length", 60, True)
    assert AuditLog.objects.filter(action="machine_session.auto_stopped", target_id=str(row.pk)).count() == 1
    after = domain_rows()
    assert run_session_sweep() == {"skipped": 0, "auto_stopped": 0, "access_expiring_notices": 0}
    assert domain_rows() == after

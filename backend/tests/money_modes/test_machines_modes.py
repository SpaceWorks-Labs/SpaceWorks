"""#184 matrix, machines: completion charges, quotes and prepay (G3), session tracking (G4)."""

from decimal import Decimal

import pytest

from apps.machines import role_scope, service_workflow_review as review
from apps.machines.models import MachineServiceRequest, MakerspaceMachineTypePolicy
from apps.machines.service_workflow import accept, complete, start
from apps.payments.availability import charge_tracking_enabled
from tests.machines.eta_helpers import job, owner, world
from tests.machines.test_job_flow import priced
from tests.money_modes.helpers import FREE, MODES, ONLINE, assert_mode_outcome, charges, fake_provider, set_mode

pytestmark = pytest.mark.django_db
S = MachineServiceRequest.Status


def machine_world(slug, mode, monkeypatch):
    w = priced(world(slug))
    set_mode(w.space, "machines", mode, extra_modules=("machines", "machine_service"))
    return w, (fake_provider(monkeypatch) if mode == ONLINE else None)


@pytest.mark.parametrize("mode", MODES)
def test_a_priced_job_runs_end_to_end_in_every_mode(mode, monkeypatch, django_capture_on_commit_callbacks):
    w, checkout = machine_world(f"mm-job-{mode}", mode, monkeypatch)
    member = owner(f"mm-job-{mode}-m")
    row = job(w, member=member)
    with django_capture_on_commit_callbacks(execute=True):
        if mode == FREE:
            # Free: no quote is needed, the job is accepted straight away.
            accept(row, w.staff, estimated_minutes=20)
            row.refresh_from_db()
        else:
            row = review.send_quote(row, w.staff, estimated_minutes=20)
            row = review.approve_quote(row, member, digest=row.quote_digest)
        assert row.status == S.ACCEPTED
        start(row, w.staff, role_scope.EXEMPT, machine_id=w.machines[0].pk)
        done = complete(row, w.staff, actual_minutes=20, consumptions=[])
    assert done.status == S.COMPLETED
    assert_mode_outcome(mode, charges(w.space, "machine_service_request"), checkout)


def test_free_machines_refuse_a_quote_and_never_prepay():
    w, _ = machine_world("mm-job-noquote", FREE, None)
    MakerspaceMachineTypePolicy.objects.create(makerspace=w.space, machine_type=w.kind, payment_timing="prepay",
                                               quote_mode="always")
    from apps.machines import job_policy
    assert job_policy.prepay(w.space, w.kind) is False
    assert job_policy.quote_required(w.space, w.kind, Decimal("50")) is False
    with pytest.raises(Exception) as refused:
        review.send_quote(job(w, member=owner("mm-noquote-m")), w.staff, estimated_minutes=10)
    assert "free" in str(refused.value).lower()


def test_a_prepaid_quote_approved_after_charges_went_off_queues_without_a_charge(monkeypatch):
    w, _ = machine_world("mm-prepay-off", "offline", monkeypatch)
    MakerspaceMachineTypePolicy.objects.create(makerspace=w.space, machine_type=w.kind, payment_timing="prepay")
    member = owner("mm-prepay-off-m")
    row = review.send_quote(job(w, member=member), w.staff, estimated_minutes=15)
    assert row.prepay
    set_mode(w.space, "machines", FREE)
    row = review.approve_quote(row, member, digest=row.quote_digest)
    assert row.status == S.ACCEPTED
    assert charges(w.space, "machine_service_request") == []


def test_the_sweep_queues_a_prepaid_job_stuck_without_a_charge(monkeypatch):
    w, _ = machine_world("mm-prepay-stuck", "offline", monkeypatch)
    MakerspaceMachineTypePolicy.objects.create(makerspace=w.space, machine_type=w.kind, payment_timing="prepay")
    member = owner("mm-prepay-stuck-m")
    row = review.send_quote(job(w, member=member), w.staff, estimated_minutes=15)
    # Approved while tracking was on, but the charge never landed (e.g. switched off mid-flight).
    from django.utils import timezone
    MachineServiceRequest.objects.filter(pk=row.pk).update(quote_approved_at=timezone.now())
    set_mode(w.space, "machines", FREE)
    queued = review.promote_prepaid(row)
    assert queued is not None and queued.status == S.ACCEPTED
    from apps.audit.models import AuditLog
    assert AuditLog.objects.get(action="machine_service.prepaid_queued", target_id=str(row.pk)).meta["free"] is True


def test_session_billing_needs_only_the_machines_module():
    """G4: `charges.machines` no longer requires `machine_service`, so sessions bill without it."""
    from apps.machines.sessions_billing import billing_active
    w = world("mm-sessions")
    set_mode(w.space, "machines", "offline", extra_modules=("machines",))
    w.space.enabled_modules = sorted(set(w.space.enabled_modules) - {"machine_service"})
    w.space.save(update_fields=["enabled_modules"])
    w.space.refresh_from_db()
    assert charge_tracking_enabled(w.space, "machines") and billing_active(w.space)
    set_mode(w.space, "machines", FREE)
    assert not billing_active(w.space)

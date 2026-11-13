"""Separate-connection PostgreSQL races for cancellation (C10/C13): no deadlock, no leak."""

from decimal import Decimal
from uuid import uuid4

import pytest

from apps.audit.models import AuditLog
from apps.devices.models import Device
from apps.devices.principal import DevicePrincipal
from apps.devices.services_commands import acknowledge, lease_command
from apps.devices.services_printer_apply import approve_report, report_result
from apps.devices.services_printer_bindings import create_binding
from apps.devices.services_printer_jobs import create_job
from apps.integrations.models_contract import NotificationEnvelope
from apps.machines import role_scope, service_consumable_pools as pools
from apps.machines.models import Machine, MachineServiceRequest, MachineType, ServiceQueue, ServiceRequestConsumption
from apps.machines.service_errors import ServiceInvalidTransition, ServiceMachineUnavailable
from apps.machines.service_workflow import accept, cancel, start
from apps.payments.models import Payment
from tests.devices.helpers import active_device
from tests.machines.eta_helpers import approved, enable, interleave, is_deadlock, job, owner, world

pytestmark = pytest.mark.django_db(transaction=True)


def fresh(row):
    return MachineServiceRequest.objects.get(pk=row.pk)


def no_deadlock(*outcomes):
    assert not any(is_deadlock(outcome) for outcome in outcomes), outcomes


def staff(w):
    return type(w.staff).objects.get(pk=w.staff.pk)


@pytest.mark.parametrize("cancel_first", [True, False])
def test_cancel_versus_start_never_leaks_or_double_refunds(cancel_first):
    w = world("race-start")
    pool = pools.create_pool(w.space, w.staff, material="Sheet", quantity="100", machine_type=w.kind)
    row = approved(w, 20, created=-5)
    do_cancel = lambda: cancel(fresh(row), staff(w))
    do_start = lambda: start(fresh(row), staff(w), role_scope.EXEMPT, machine_id=w.machines[0].pk,
                             consumable_pool_id=pool.pk, planned_grams="30")
    first, second = interleave(*((do_cancel, do_start) if cancel_first else (do_start, do_cancel)))
    no_deadlock(first, second)
    if cancel_first:
        assert isinstance(second, ServiceInvalidTransition)
    pool.refresh_from_db()
    assert pool.remaining_grams == Decimal("100.00")
    assert fresh(row).status == "cancelled" and fresh(row).reserved_grams == 0
    assert Machine.objects.get(pk=w.machines[0].pk).status == Machine.Status.IDLE


@pytest.mark.parametrize("capacity", [1, None])
@pytest.mark.parametrize("cancel_first", [True, False])
def test_cancel_versus_start_capacity_and_a_machine_flagged_idle_while_running(cancel_first, capacity):
    w = world("race-capacity", capacity=capacity)
    running = approved(w, 30, created=-10)
    start(running, w.staff, role_scope.EXEMPT, machine_id=w.machines[0].pk)
    Machine.objects.filter(pk=w.machines[0].pk).update(status=Machine.Status.IDLE)  # set_status drift (C8)
    waiting = approved(w, 10, created=-5)
    do_cancel = lambda: cancel(fresh(running), staff(w))
    do_start = lambda: start(fresh(waiting), staff(w), role_scope.EXEMPT, machine_id=w.machines[0].pk)
    first, second = interleave(*((do_cancel, do_start) if cancel_first else (do_start, do_cancel)))
    no_deadlock(first, second)
    started = second if cancel_first else first
    assert fresh(running).status == "cancelled"
    if capacity == 1 or not cancel_first:
        # The running job still held its queue slot / its machine when start counted or looked:
        # the count may over-count (C13) and the flag never wins over a running row (C8).
        assert isinstance(started, ServiceMachineUnavailable)
        start(fresh(waiting), staff(w), role_scope.EXEMPT, machine_id=w.machines[0].pk)
    else:
        assert not isinstance(started, Exception), started  # waited for the machine lock, then ran
    assert fresh(waiting).status == "in_progress"


def test_duplicate_concurrent_cancels_release_audit_and_notify_once():
    w = world("race-duplicate")
    member = owner("race-duplicate")
    pool = pools.create_pool(w.space, w.staff, material="Sheet", quantity="100", machine_type=w.kind)
    row = approved(w, 20, created=-5, member=member)
    start(row, w.staff, role_scope.EXEMPT, machine_id=w.machines[0].pk, consumable_pool_id=pool.pk, planned_grams="30")
    first, second = interleave(lambda: cancel(fresh(row), staff(w)),
                               lambda: cancel(fresh(row), type(member).objects.get(pk=member.pk), by_owner=True))
    no_deadlock(first, second)
    pool.refresh_from_db()
    assert pool.remaining_grams == Decimal("100.00")
    assert AuditLog.objects.filter(action="machine_service.cancelled", target_id=str(row.pk)).count() == 1
    assert NotificationEnvelope.objects.filter(source_id=str(row.pk), event="cancelled", audience="requester").count() == 1


@pytest.mark.parametrize("with_pool", [True, False])
@pytest.mark.parametrize("cancel_first", [True, False])
def test_pooled_cancel_versus_linked_manual_usage(with_pool, cancel_first):
    w = world("race-manual")
    pool = pools.create_pool(w.space, w.staff, material="Sheet", quantity="100", machine_type=w.kind)
    row = approved(w, 20, created=-5)
    start(row, w.staff, role_scope.EXEMPT, machine_id=w.machines[0].pk, consumable_pool_id=pool.pk, planned_grams="30")
    machine = w.machines[0]
    do_cancel = lambda: cancel(fresh(row), staff(w))
    do_usage = lambda: pools.log_typed_manual_usage(
        Machine.objects.get(pk=machine.pk), staff(w), duration_minutes=5, outcome="success", percent_complete=100,
        grams="5" if with_pool else "0", pool=pool if with_pool else None, service_request=fresh(row))
    first, second = interleave(*((do_cancel, do_usage) if cancel_first else (do_usage, do_cancel)))
    no_deadlock(first, second)
    assert not isinstance(first, Exception) and not isinstance(second, Exception), (first, second)
    pool.refresh_from_db()
    assert pool.remaining_grams == Decimal("95.00" if with_pool else "100.00")
    assert fresh(row).status == "cancelled" and fresh(row).reserved_grams == 0


def device_case(slug, *, auto=True, pooled=True):
    space, manager, _client, device_id, _private = active_device(f"{slug}-{uuid4().hex[:6]}")
    enable(space, off=("membership",))
    kind = MachineType.objects.create(makerspace=space, slug=f"{slug}-{uuid4().hex[:6]}", name="Bound printer")
    machines = [Machine.objects.create(makerspace=space, machine_type=kind, name=f"P{i}") for i in range(2)]
    queue = ServiceQueue.objects.create(makerspace=space, machine_type=kind, name="Bound queue")
    member = owner(slug)
    from apps.machines.service_workflow import submit
    row = submit(queue if pooled else machines[0], member, member=member, actor=member, requester_name="O",
                 contact_email=member.email, contact_phone="", title="Device job")
    accept(row, manager, estimated_minutes=15)
    start(row, manager, role_scope.EXEMPT, machine_id=machines[0].pk)
    binding = create_binding(manager, space.pk, device_id=device_id, machine_id=machines[0].pk, auto_apply_terminal=auto)
    principal = DevicePrincipal.from_device(Device.objects.get(pk=device_id))
    return space, manager, queue, machines, member, row, binding, principal


def leased_job(manager, space, binding, row, principal):
    printer_job = create_job(manager, space.pk, binding_id=binding.pk, service_request_id=row.pk, external_job_id="job-" + uuid4().hex)
    lease = lease_command(principal)
    acknowledge(principal, printer_job.command_id, lease["lease_token"])
    return printer_job


def payload(printer_job):
    return {"operation_id": str(uuid4()), "external_job_id": printer_job.external_job_id, "outcome": "completed",
            "actual_minutes": 15, "consumptions": []}


def assert_no_completion_effects(row):
    assert not ServiceRequestConsumption.objects.filter(service_request=row).exists()
    assert not Payment.objects.filter(subject_type="machine_service_request", subject_id=row.pk).exists()


@pytest.mark.parametrize("cancel_first", [True, False])
def test_device_auto_apply_versus_pooled_cancel(cancel_first):
    space, manager, _queue, _machines, _member, row, binding, principal = device_case("race-device")
    printer_job = leased_job(manager, space, binding, row, principal)
    do_cancel = lambda: cancel(fresh(row), type(manager).objects.get(pk=manager.pk))
    do_apply = lambda: report_result(principal, printer_job.pk, payload(printer_job))
    first, second = interleave(*((do_cancel, do_apply) if cancel_first else (do_apply, do_cancel)))
    no_deadlock(first, second)
    final = fresh(row)
    if cancel_first:
        assert final.status == "cancelled" and isinstance(second, Exception)  # live_target refuses
        assert_no_completion_effects(final)
    else:
        assert final.status == "completed" and isinstance(second, ServiceInvalidTransition)
        assert NotificationEnvelope.objects.filter(source_id=str(row.pk), event="completed", audience="requester").count() == 1


def test_device_report_after_cancellation_is_refused_without_completion_debit_or_charge():
    space, manager, _queue, _machines, _member, row, binding, principal = device_case("race-late-report")
    printer_job = leased_job(manager, space, binding, row, principal)
    cancel(fresh(row), manager)
    with pytest.raises(Exception):
        report_result(principal, printer_job.pk, payload(printer_job))
    assert fresh(row).status == "cancelled"
    assert_no_completion_effects(row)
    assert not NotificationEnvelope.objects.filter(source_id=str(row.pk), event="completed").exists()


@pytest.mark.parametrize("cancel_first", [True, False])
def test_staff_approve_report_versus_pooled_cancel(cancel_first):
    space, manager, _queue, _machines, _member, row, binding, principal = device_case("race-approve", auto=False)
    printer_job = leased_job(manager, space, binding, row, principal)
    claimed = report_result(principal, printer_job.pk, payload(printer_job))
    assert claimed.state == "needs_review"
    do_cancel = lambda: cancel(fresh(row), type(manager).objects.get(pk=manager.pk))
    do_approve = lambda: approve_report(type(manager).objects.get(pk=manager.pk), claimed.pk)
    first, second = interleave(*((do_cancel, do_approve) if cancel_first else (do_approve, do_cancel)))
    no_deadlock(first, second)
    assert fresh(row).status == ("cancelled" if cancel_first else "completed")
    if cancel_first:
        assert_no_completion_effects(row)


@pytest.mark.parametrize("other", ["submit", "start"])
def test_device_auto_apply_versus_pooled_submit_and_start(other):
    space, manager, queue, machines, member, row, binding, principal = device_case(f"race-{other}")
    printer_job = leased_job(manager, space, binding, row, principal)
    waiting = None
    if other == "start":
        waiting = approved_job = submit_job(queue, member)
        accept(approved_job, manager, estimated_minutes=10)
    from apps.machines.service_workflow import submit as submit_workflow

    def do_other():
        if other == "submit":
            return submit_workflow(ServiceQueue.objects.get(pk=queue.pk), member, member=member, actor=member,
                                   requester_name="O", contact_email=member.email, contact_phone="", title="New")
        return start(fresh(waiting), type(manager).objects.get(pk=manager.pk), role_scope.EXEMPT, machine_id=machines[1].pk)

    first, second = interleave(lambda: report_result(principal, printer_job.pk, payload(printer_job)), do_other)
    no_deadlock(first, second)
    assert not isinstance(first, Exception) and not isinstance(second, Exception), (first, second)
    assert fresh(row).status == "completed"


def submit_job(queue, member):
    from apps.machines.service_workflow import submit
    return submit(queue, member, member=member, actor=member, requester_name="O", contact_email=member.email,
                  contact_phone="", title="Second")


@pytest.mark.parametrize("cancel_first", [True, False])
def test_device_create_job_versus_bucket_cancel(cancel_first):
    space, manager, _queue, _machines, _member, row, binding, _principal = device_case("race-create", pooled=False)
    do_cancel = lambda: cancel(fresh(row), type(manager).objects.get(pk=manager.pk))
    do_create = lambda: create_job(type(manager).objects.get(pk=manager.pk), space.pk, binding_id=binding.pk,
                                   service_request_id=row.pk, external_job_id="job-" + uuid4().hex)
    first, second = interleave(*((do_cancel, do_create) if cancel_first else (do_create, do_cancel)))
    no_deadlock(first, second)
    assert fresh(row).status == "cancelled"
    if cancel_first:
        assert isinstance(second, Exception)  # no job for a request that is no longer running

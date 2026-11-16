"""Cancellation by requester and staff: release with zero consumption, no charge, recompute."""

from decimal import Decimal

import pytest

from apps.audit.models import AuditLog
from apps.machines import role_scope, service_consumable_pools as pools
from apps.machines.models import (
    Machine, MachineConsumableAdjustment, MachineServiceRequest, MachineType, ServiceBucket,
    ServiceRequestConsumption,
)
from apps.machines.service_errors import ServiceInvalidTransition
from apps.machines.service_queue_eta import machine_queue_summaries_for, queue_snapshot_for
from apps.machines.service_workflow import cancel, collect, complete, fail, reject, start
from apps.machines.service_workflow_cancel import CancelRefused
from apps.payments.models import Payment
from tests.machines.eta_helpers import NOW, approved, job, owner, owner_fixture, pending, world

pytestmark = pytest.mark.django_db


def pool_for(w, *, unit="grams", amount="100"):
    return pools.create_pool(w.space, w.staff, material="Sheet", quantity=amount, machine_type=w.kind, unit=unit)


def seed_hold(w, row, kind):
    """Seed a hold of each shape the kernel can produce, on any non-terminal row."""
    machine = w.machines[0]
    if kind == "weight":
        pool = pool_for(w)
        pools.reserve_for_request(row, w.staff, pool=pool, planned_grams="20", machine=machine)
    elif kind == "legacy_weight":
        pool = pool_for(w)
        pools._legacy_reserve_for_request(row, w.staff, pool=pool, planned_grams="20", machine=machine)
    elif kind == "count":
        MachineType.objects.filter(pk=w.kind.pk).update(capability_config={"metering_unit": "count", "requires_booking": False})
        w.kind.refresh_from_db()
        machine.refresh_from_db()
        pool = pool_for(w, unit="count", amount="10")
        pools.reserve_for_request(row, w.staff, pool=pool, planned_quantity="4", machine=machine)
    elif kind == "grams_on_count_pool":
        pool = pool_for(w, unit="count", amount="50")
        pools._legacy_reserve_for_request(row, w.staff, pool=pool, planned_grams="20", machine=machine)
    else:
        return None
    pool.refresh_from_db()
    return pool


def assert_released(row, pool):
    row.refresh_from_db()
    assert row.reserved_grams == Decimal("0") and row.reserved_quantity in (None, Decimal("0"))
    assert row.actual_consumed_grams == Decimal("0") and row.actual_consumed_quantity in (None, Decimal("0"))
    if pool is not None:
        pool.refresh_from_db()
        assert pool.remaining_grams == pool.initial_grams
        deltas = list(MachineConsumableAdjustment.objects.filter(service_request=row).values_list("kind", "quantity_delta"))
        assert [kind for kind, _ in deltas] == ["reserve", "reconcile"] and sum(d for _, d in deltas) == 0
        assert AuditLog.objects.filter(action="machine_consumable_pool.reconcile").exists()
    assert not ServiceRequestConsumption.objects.filter(service_request=row).exists()
    assert not Payment.objects.filter(subject_type="machine_service_request", subject_id=row.pk).exists()


@pytest.mark.parametrize("by_owner", [True, False])
@pytest.mark.parametrize("stage", ["pending", "accepted", "in_progress"])
@pytest.mark.parametrize("hold", ["weight", "legacy_weight", "count", "grams_on_count_pool", None])
def test_cancel_releases_every_hold_shape_with_zero_charge(by_owner, stage, hold):
    w = world(f"cancel-{stage}")
    member = owner("cancel-owner")
    row = job(w, member=member) if stage == "pending" else approved(w, 30, created=-5, member=member)
    if stage == "in_progress":
        start(row, w.staff, role_scope.EXEMPT, machine_id=w.machines[0].pk)
    pool = seed_hold(w, row, hold)
    actor = member if by_owner else w.staff
    if by_owner and stage == "in_progress":
        # #141/#142: a member cancels only before In progress; staff stop a running job.
        with pytest.raises(CancelRefused):
            cancel(row, actor, reason="Changed my mind", by_owner=True)
        return
    cancelled = cancel(row, actor, reason="Changed my mind", by_owner=by_owner)
    assert cancelled.status == "cancelled" and cancelled.cancelled_at is not None
    assert_released(row, pool)
    audit = AuditLog.objects.get(action="machine_service.cancelled", target_id=str(row.pk))
    assert audit.meta["previous_status"] == stage and audit.meta["cancelled_by"] == ("owner" if by_owner else "staff")
    assert (audit.meta["released_hold"] is not None) == (hold is not None)
    machine = Machine.objects.get(pk=w.machines[0].pk)
    assert machine.status == Machine.Status.IDLE
    cancel(row, actor, by_owner=by_owner)
    assert AuditLog.objects.filter(action="machine_service.cancelled", target_id=str(row.pk)).count() == 1
    assert MachineConsumableAdjustment.objects.filter(service_request=row, kind="reconcile").count() == (1 if hold else 0)


def test_cancelling_a_waiting_bucket_job_never_idles_someone_elses_running_job():
    w = world("cancel-bucket")
    machine = w.machines[0]
    runner = job(w, target=machine)
    waiting = job(w, target=machine)
    from apps.machines.service_workflow import accept
    accept(runner, w.staff, estimated_minutes=30)
    start(runner, w.staff, role_scope.EXEMPT, machine_id=machine.pk)
    accept(waiting, w.staff, estimated_minutes=10)
    cancel(waiting, w.staff)
    machine.refresh_from_db()
    assert machine.status == Machine.Status.RUNNING
    assert ServiceBucket.objects.filter(machine=machine).count() == 1


def test_pending_reject_releases_a_seeded_hold_and_keeps_its_meaning():
    w = world("cancel-reject")
    row = job(w)
    pool = seed_hold(w, row, "weight")
    reject(row, w.staff, reason="Not suitable")
    row.refresh_from_db()
    assert row.status == "rejected"
    assert_released(row, pool)
    audit = AuditLog.objects.get(action="machine_service.rejected", target_id=str(row.pk))
    assert audit.meta["released_hold"]["released_grams"] == "20.00"


def test_terminal_jobs_cannot_be_cancelled():
    w = world("cancel-terminal")
    done = approved(w, 10, created=-5)
    start(done, w.staff, role_scope.EXEMPT, machine_id=w.machines[0].pk)
    complete(done, w.staff, actual_minutes=10, consumptions=[])
    with pytest.raises(ServiceInvalidTransition):
        cancel(done, w.staff)
    collect(done, w.staff)
    with pytest.raises(ServiceInvalidTransition):
        cancel(done, w.staff)
    failed = approved(w, 10, created=-4)
    start(failed, w.staff, role_scope.EXEMPT, machine_id=w.machines[1].pk)
    fail(failed, w.staff, reason="Jam", percent_complete=10, actual_minutes=1, consumptions=[])
    rejected = job(w)
    reject(rejected, w.staff, reason="No")
    for row in (failed, rejected):
        with pytest.raises(ServiceInvalidTransition):
            cancel(row, w.staff)


def test_non_owner_and_foreign_staff_are_refused_under_lock():
    w, foreign = world("cancel-deny"), world("cancel-deny-foreign")
    row = job(w)
    with pytest.raises(CancelRefused):
        cancel(row, owner("cancel-stranger"), by_owner=True)
    with pytest.raises(CancelRefused):
        cancel(row, foreign.staff)
    row.refresh_from_db()
    assert row.status == "pending"


def test_post_cancel_reads_recompute_the_shortened_timeline_immediately():
    w = world("cancel-recompute")
    case = owner_fixture(w)
    cancel(case.second, w.staff)
    snapshot = queue_snapshot_for([case.target], now=NOW)
    assert (snapshot.eta(case.target)["start_in_minutes"], snapshot.eta(case.target)["finish_in_minutes"]) == (30, 45)
    assert snapshot.eta(MachineServiceRequest.objects.get(pk=case.second.pk)) is None
    fresh = world("cancel-recompute-running")
    other = owner_fixture(fresh)
    cancel(other.run_b, fresh.staff)
    snapshot = queue_snapshot_for([other.first, other.second, other.target], now=NOW)
    assert snapshot.eta(other.first)["finish_in_minutes"] == 60      # B 10:00-11:00
    assert (snapshot.eta(other.second)["start_in_minutes"], snapshot.eta(other.second)["finish_in_minutes"]) == (10, 30)
    assert (snapshot.eta(other.target)["start_in_minutes"], snapshot.eta(other.target)["finish_in_minutes"]) == (30, 45)
    summaries = machine_queue_summaries_for(fresh.machines, now=NOW)
    assert (summaries[fresh.machines[0].pk]["eta_minutes"], summaries[fresh.machines[1].pk]["eta_minutes"]) == (45, 60)


@pytest.mark.parametrize("type_name", ["CNC router", "Vinyl cutter", "Embroidery machine", "Locally configured rig"])
def test_every_machine_type_gets_the_same_pooled_forecast(type_name):
    w = world("eta-type", type_name=type_name)
    case = owner_fixture(w)
    value = queue_snapshot_for([case.target], now=NOW).eta(case.target)
    assert (value["start_in_minutes"], value["finish_in_minutes"], value["confidence"]) == (50, 65, "estimated")


def test_bucket_jobs_forecast_on_their_own_machine():
    w = world("eta-bucket", type_name="Vinyl cutter")
    machine = w.machines[0]
    first = approved(w, 30, created=-10, target=machine)
    second = approved(w, 20, created=-5, target=machine)
    snapshot = queue_snapshot_for([first, second], now=NOW)
    assert snapshot.eta(second)["start_in_minutes"] == 30 and snapshot.eta(second)["finish_in_minutes"] == 50
    assert pending(w, 5, created=-1, target=machine).status == "pending"

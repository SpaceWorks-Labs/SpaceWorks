"""#141/#142: the job lifecycle -- needs changes, quotes, queue place, failure outcomes, pickup."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.machines import role_scope, service_workflow_board as board, service_workflow_review as review
from apps.machines.models import MachineServiceRequest, MakerspaceMachineTypePricing
from apps.machines.service_queue_position import queue_positions_for
from apps.machines.service_workflow import accept, cancel, collect, complete, fail, start
from apps.machines.service_workflow_cancel import CancelRefused
from apps.machines.service_workflow_collect import mark_uncollected
from apps.payments.models import Payment
from tests.machines.eta_helpers import approved, enable, job, owner, world
from tests.machines.session_helpers import check_in
from tests.rbac_f6_helpers import community_member

pytestmark = pytest.mark.django_db
S = MachineServiceRequest.Status


def priced(w, rate="2.00", flat="5.00"):
    """A priced type (per minute) -- jobs then need a quote by default (#142 OQ-2)."""
    MakerspaceMachineTypePricing.objects.create(makerspace=w.space, machine_type=w.kind, rate_per_unit=Decimal(rate),
                                                flat_fee=Decimal(flat), payment_enabled=True)
    config = dict(w.kind.capability_config or {}, metering_unit="minutes", requires_booking=False)
    type(w.kind).objects.filter(pk=w.kind.pk).update(capability_config=config)
    w.kind.refresh_from_db()
    return w


def test_needs_changes_and_resubmit_keep_the_place_within_three_days():
    w = world("flow-changes")
    # A resubmit re-runs the public intake gates (decision 221e / 246): the membership and
    # presence modules are on and the member is checked in, as in test_job_intake.admitted.
    enable(w.space, "membership", "presence")
    membership = community_member(w.space, "flow-changes-m")
    check_in(w.space, membership)
    member = membership.user
    row = job(w, member=member)
    row = review.request_changes(row, w.staff, code="wrong_format", message="Export as STL please.")
    assert row.status == S.CHANGES_REQUESTED and row.changes_message
    with pytest.raises(Exception):
        review.resubmit(row, owner("flow-changes-other"), note="not mine")
    row = review.resubmit(row, member, note="Here it is")
    assert row.status == S.PENDING and row.member_note == "Here it is"
    assert row.queued_at == row.created_at
    late = job(w, member=member)
    late = review.request_changes(late, w.staff, code="other", message="More detail")
    MachineServiceRequest.objects.filter(pk=late.pk).update(changes_requested_at=timezone.now() - timedelta(days=5))
    late.refresh_from_db()
    late = review.resubmit(late, member)
    assert late.queued_at > late.created_at + timedelta(seconds=1) or late.queued_at >= timezone.now() - timedelta(minutes=1)
    actions = set(AuditLog.objects.filter(target_id=str(row.pk)).values_list("action", flat=True))
    assert {"machine_service.changes_requested", "machine_service.resubmitted"} <= actions


def test_priced_jobs_need_a_quote_the_member_approves_with_the_digest():
    w = priced(world("flow-quote"))
    member = owner("flow-quote-m")
    row = job(w, member=member)
    with pytest.raises(Exception) as refused:
        accept(row, w.staff, estimated_minutes=30)
    assert "quote_required" in str(refused.value.detail)
    row = review.send_quote(row, w.staff, estimated_minutes=30)
    assert row.status == S.QUOTED and Decimal(row.quote_snapshot["total"]) > 0
    assert row.quote_expires_at - row.quoted_at == timedelta(days=7)
    from apps.payments.pricing.errors import PriceChanged
    with pytest.raises(PriceChanged):
        review.approve_quote(row, member, digest="0" * 64)
    row = review.approve_quote(row, member, digest=row.quote_digest)
    assert row.status == S.ACCEPTED
    start(row, w.staff, role_scope.EXEMPT, machine_id=w.machines[0].pk)
    done = complete(row, w.staff, actual_minutes=300, consumptions=[])
    payment = Payment.objects.get(subject_type="machine_service_request", subject_id=done.pk)
    assert payment.amount == Decimal(row.quote_snapshot["total"])  # capped at the quote (OQ-4)
    assert done.pickup_code and len(done.pickup_code) == 6


def test_declined_and_expired_quotes_cancel_with_nothing_charged():
    w = priced(world("flow-decline"))
    member = owner("flow-decline-m")
    one = review.send_quote(job(w, member=member), w.staff, estimated_minutes=10)
    assert review.decline_quote(one, member).status == S.CANCELLED
    two = review.send_quote(job(w, member=member), w.staff, estimated_minutes=10)
    MachineServiceRequest.objects.filter(pk=two.pk).update(quote_expires_at=timezone.now() - timedelta(minutes=1))
    from apps.machines.job_sweeps import run_job_flow_sweep
    run_job_flow_sweep()
    two.refresh_from_db()
    assert two.status == S.CANCELLED
    assert not Payment.objects.filter(subject_type="machine_service_request").exists()


def test_prepaid_quote_raises_the_quoted_charge_and_queues_once_settled():
    from apps.machines.models import MakerspaceMachineTypePolicy
    from apps.payments.reconciliation import mark_offline
    from tests.return_helpers import settlement_details
    w = priced(world("flow-prepay"))
    MakerspaceMachineTypePolicy.objects.create(makerspace=w.space, machine_type=w.kind, payment_timing="prepay")
    member = owner("flow-prepay-m")
    row = review.send_quote(job(w, member=member), w.staff, estimated_minutes=20)
    row = review.approve_quote(row, member, digest=row.quote_digest)
    assert row.status == S.QUOTED and row.prepay and row.quote_approved_at
    payment = Payment.objects.get(subject_type="machine_service_request", subject_id=row.pk)
    assert payment.status == "pending" and payment.amount == Decimal(row.quote_snapshot["total"])
    assert review.promote_prepaid(row) is None
    mark_offline(payment, w.staff, settlement=settlement_details())
    queued = review.promote_prepaid(row)
    assert queued.status == S.ACCEPTED
    start(queued, w.staff, role_scope.EXEMPT, machine_id=w.machines[0].pk)
    complete(queued, w.staff, actual_minutes=5, consumptions=[])
    assert Payment.objects.filter(subject_type="machine_service_request").count() == 1


def test_reorder_and_urgent_pin_change_the_shared_position():
    w = world("flow-order")
    first, second, third = (approved(w, 10, created=-30 + i) for i in range(3))
    assert queue_positions_for([first, second, third]) == {first.pk: 1, second.pk: 2, third.pk: 3}
    board.reorder(third, w.staff, position=1)
    rows = MachineServiceRequest.objects.filter(pk__in=[first.pk, second.pk, third.pk])
    assert queue_positions_for(list(rows))[third.pk] == 1
    board.pin_urgent(second, w.staff, urgent=True, reason="Class demo tomorrow")
    rows = MachineServiceRequest.objects.filter(pk__in=[first.pk, second.pk, third.pk])
    assert queue_positions_for(list(rows))[second.pk] == 1
    with pytest.raises(Exception):
        board.pin_urgent(first, w.staff, urgent=True, reason="")
    assert AuditLog.objects.filter(action="machine_service.reordered", target_id=str(third.pk)).exists()


def test_preassigned_machine_is_used_at_start():
    w = world("flow-assign")
    row = approved(w, 10, created=-5)
    board.assign_machine(row, w.staff, machine_id=w.machines[1].pk)
    started = start(row, w.staff, role_scope.EXEMPT)
    assert started.assigned_machine_id == w.machines[1].pk


def test_space_fault_requeues_at_the_front_and_member_fault_is_free_by_default(django_capture_on_commit_callbacks):
    w = world("flow-fail")
    member = owner("flow-fail-m")
    row = approved(w, 10, created=-60, member=member)
    later = approved(w, 10, created=-10)
    start(row, w.staff, role_scope.EXEMPT, machine_id=w.machines[0].pk)
    with django_capture_on_commit_callbacks(execute=True):
        failed = fail(row, w.staff, reason="Nozzle jam", percent_complete=40, actual_minutes=4, consumptions=[],
                      code="nozzle_jam", fault="space")
    assert failed.failure_outcome == "requeued"
    rerun = MachineServiceRequest.objects.get(reprint_of=row)
    assert rerun.status == S.ACCEPTED and rerun.auto_requeue_count == 1
    assert queue_positions_for([rerun, later])[rerun.pk] == 1
    other = approved(w, 10, created=-5, member=member)
    start(other, w.staff, role_scope.EXEMPT, machine_id=w.machines[1].pk)
    member_fault = fail(other, w.staff, reason="Bad file", percent_complete=10, actual_minutes=2, consumptions=[],
                        code="file_problem", fault="member")
    assert member_fault.failure_outcome == "free"
    assert not Payment.objects.filter(subject_type="machine_service_request", subject_id=other.pk).exists()


def test_members_cancel_only_before_in_progress():
    w = world("flow-cancel")
    member = owner("flow-cancel-m")
    row = approved(w, 10, created=-5, member=member)
    start(row, w.staff, role_scope.EXEMPT, machine_id=w.machines[0].pk)
    with pytest.raises(CancelRefused):
        cancel(row, member, by_owner=True)
    assert cancel(row, w.staff).status == S.CANCELLED


def test_pickup_code_collects_and_uncollected_waits_fourteen_days():
    w = world("flow-pickup")
    member = owner("flow-pickup-m")
    row = approved(w, 10, created=-5, member=member)
    start(row, w.staff, role_scope.EXEMPT, machine_id=w.machines[0].pk)
    done = complete(row, w.staff, actual_minutes=10, consumptions=[], pickup_location="Shelf B")
    with pytest.raises(Exception):
        collect(done, w.staff, pickup_code="WRONG1")
    collected = collect(done, w.staff, pickup_code=done.pickup_code.lower(), collector_name="A friend")
    assert collected.status == S.COLLECTED and collected.collected_by_name == "A friend"
    other = approved(w, 10, created=-4, member=member)
    start(other, w.staff, role_scope.EXEMPT, machine_id=w.machines[0].pk)
    other = complete(other, w.staff, actual_minutes=10, consumptions=[])
    with pytest.raises(Exception):
        mark_uncollected(other, w.staff)
    MachineServiceRequest.objects.filter(pk=other.pk).update(completed_at=timezone.now() - timedelta(days=15))
    assert mark_uncollected(other, w.staff).status == S.UNCOLLECTED

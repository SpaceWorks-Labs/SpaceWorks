"""Mutation pins (decision 457, MUT-A): submit/accept/reject/cancel/expire exact side effects.

Each test asserts an exact audit action + meta, an exact state or an exact stock count through the
workflow module, so a dropped call, a renamed audit key or an off-by-one boundary fails here.
"""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.hardware_requests import request_lifecycle, waitlist, workflow
from apps.hardware_requests.models import HardwareRequest
from apps.hardware_requests.models_loans import LoanReservationPolicy, LoanWaitlistEntry as Entry
from apps.hardware_requests.workflow_errors import InvalidTransition, RequestValidationError
from apps.inventory.models import InventoryProduct
from apps.managed_hosting.extra_quotas import ExtraQuotaReached
from apps.space_controls.models import SpaceControlState
from tests.hardware_requests.test_new_states import space_with, submit
from tests.return_helpers import make_member, make_product, make_user

pytestmark = pytest.mark.django_db


class Boom(Exception):
    pass


def stock(product):
    product.refresh_from_db()
    return product.available_quantity, product.reserved_quantity


def audit_meta(action, request):
    return AuditLog.objects.get(action=action, target_id=str(request.pk)).meta


# ---- submit_request: the three guards run, in the tenant's own terms -------------------------------------


def test_submit_runs_the_source_gate_with_the_space_id_before_creating_anything():
    space = space_with("mp-gate")
    product = make_product(space)
    member = make_user("mp-gate-m", access_status="active")
    with patch("apps.tenant_migration.gate_runtime.assert_write_allowed", side_effect=Boom) as gate:
        with pytest.raises(Boom):
            submit(space, member, product)
    gate.assert_called_once_with(space.id)
    assert HardwareRequest.objects.filter(makerspace=space).count() == 0


def test_submit_runs_the_pii_write_fence_with_the_space_id_before_creating_anything():
    space = space_with("mp-fence")
    product = make_product(space)
    member = make_user("mp-fence-m", access_status="active")
    with patch("apps.encryption.write_fence.assert_mapped_write_allowed", side_effect=Boom) as fence:
        with pytest.raises(Boom):
            submit(space, member, product)
    fence.assert_called_once_with(space.id)
    assert HardwareRequest.objects.filter(makerspace=space).count() == 0


def test_submit_counts_hardware_requests_against_the_monthly_allowance():
    space = space_with("mp-quota")
    space.resource_limit_overrides = {"hardware_requests_monthly": 1}
    space.save(update_fields=["resource_limit_overrides"])
    product = make_product(space, available_quantity=5, total_quantity=5)
    first = submit(space, make_user("mp-quota-a", access_status="active"), product)
    assert first.status == HardwareRequest.Status.PENDING_APPROVAL
    with pytest.raises(ExtraQuotaReached) as caught:
        submit(space, make_user("mp-quota-b", access_status="active"), product)
    assert caught.value.code == "hardware_requests_monthly_quota_reached"
    assert int(caught.value.detail["limit"]) == 1
    assert HardwareRequest.objects.filter(makerspace=space).count() == 1


# ---- reject_request ----------------------------------------------------------------------------------


def _claimed_waitlist_request(slug, django_capture_on_commit_callbacks):
    """A pending request that claimed a waitlist offer: its unit is held (0 available, 1 reserved)."""
    space = space_with(slug, "loans.waitlist")
    staff = make_member(f"{slug}-sm", space)
    product = make_product(space, available_quantity=1, total_quantity=1)
    holder = make_user(f"{slug}-holder", access_status="active")
    waiter = make_member(f"{slug}-waiter", space, membership_role="custom", role=User.Role.REQUESTER)
    loan = workflow.accept_request(staff, submit(space, holder, product))
    entry = waitlist.join(waiter, product, 1)
    with django_capture_on_commit_callbacks(execute=True):
        workflow.cancel_request(staff, loan, by_owner=False)
    entry.refresh_from_db()
    assert (entry.status, entry.held_quantity) == ("offered", 1)
    with django_capture_on_commit_callbacks(execute=True):
        claimed = submit(space, waiter, product, waitlist_entry_id=entry.pk)
    entry.refresh_from_db()
    assert entry.status == Entry.Status.CLAIMED and stock(product) == (0, 1)
    return space, staff, product, entry, claimed


def test_reject_releases_a_claimed_waitlist_hold_and_audits_the_trimmed_reason(django_capture_on_commit_callbacks):
    space, staff, product, entry, claimed = _claimed_waitlist_request("mp-reject", django_capture_on_commit_callbacks)
    with django_capture_on_commit_callbacks(execute=True):
        rejected = workflow.reject_request(staff, claimed, "  not this month  ")
    assert rejected.status == HardwareRequest.Status.REJECTED and rejected.rejection_reason == "not this month"
    entry.refresh_from_db()
    assert (entry.status, entry.held_quantity) == (Entry.Status.LAPSED, 0)
    assert stock(product) == (1, 0)
    assert audit_meta("request.rejected", claimed) == {"reason": "not this month"}


def test_reject_refuses_a_blank_reason_and_a_decided_request():
    space = space_with("mp-reject-refuse")
    staff = make_member("mp-reject-refuse-sm", space)
    product = make_product(space)
    request = submit(space, make_user("mp-reject-refuse-m", access_status="active"), product)
    with pytest.raises(RequestValidationError, match="Rejection reason is required."):
        workflow.reject_request(staff, request, "   ")
    workflow.reject_request(staff, request, "no")
    with pytest.raises(InvalidTransition, match="Cannot reject hardware request with status rejected."):
        workflow.reject_request(staff, request, "again")


# ---- cancel_request ----------------------------------------------------------------------------------


def test_cancel_releases_a_claimed_waitlist_hold(django_capture_on_commit_callbacks):
    space, staff, product, entry, claimed = _claimed_waitlist_request("mp-cancel-claim", django_capture_on_commit_callbacks)
    with django_capture_on_commit_callbacks(execute=True):
        workflow.cancel_request(staff, claimed, by_owner=False, reason="changed mind")
    entry.refresh_from_db()
    assert (entry.status, entry.held_quantity) == (Entry.Status.LAPSED, 0)
    assert stock(product) == (1, 0)


def test_cancel_audits_exact_meta_with_the_reason_trimmed_and_capped_at_500():
    space = space_with("mp-cancel-meta")
    staff = make_member("mp-cancel-meta-sm", space)
    product = make_product(space, available_quantity=3, total_quantity=3)
    accepted = workflow.accept_request(staff, submit(space, make_user("mp-cancel-a", access_status="active"), product, 2))
    long_reason = "x" * 600
    workflow.cancel_request(staff, accepted, by_owner=False, reason=f"  {long_reason}  ")
    assert audit_meta("request.cancelled", accepted) == {
        "from_status": "accepted", "by_owner": False, "reason": "x" * 500, "released_units": 2}
    pending = submit(space, make_user("mp-cancel-b", access_status="active"), product)
    workflow.cancel_request(staff, pending, by_owner=False, reason="  duplicate ")
    assert audit_meta("request.cancelled", pending) == {
        "from_status": "pending_approval", "by_owner": False, "reason": "duplicate", "released_units": 0}
    accepted.refresh_from_db()
    assert accepted.status == HardwareRequest.Status.CANCELLED and accepted.closed_by_id == staff.pk
    assert accepted.closed_at is not None
    assert stock(product) == (3, 0)


def test_cancel_notifies_the_requester_that_it_was_cancelled():
    space = space_with("mp-cancel-notify")
    staff = make_member("mp-cancel-notify-sm", space)
    request = submit(space, make_user("mp-cancel-notify-m", access_status="active"), make_product(space))
    with patch("apps.hardware_requests.notifications_loans.notify_closed") as notify:
        workflow.cancel_request(staff, request, by_owner=False)
    notify.assert_called_once()
    row, event = notify.call_args.args
    assert row.pk == request.pk and event == "cancelled"


def test_owner_may_cancel_needs_a_signed_in_owner_a_cancellable_status_and_the_switch():
    space = space_with("mp-owner", "loans.withdrawals")
    member = make_user("mp-owner-m", access_status="active")
    other = make_user("mp-owner-o", access_status="active")
    request = submit(space, member, make_product(space))
    assert request_lifecycle.owner_may_cancel(member, request) is True
    # Another signed-in account is not the owner (a chain of `or` would let it through).
    assert request_lifecycle.owner_may_cancel(other, request) is False
    # An actor object that never says it is authenticated is not authenticated.
    bare = SimpleNamespace(pk=member.pk)
    assert request_lifecycle.owner_may_cancel(bare, request) is False
    assert request_lifecycle.owner_may_cancel(SimpleNamespace(pk=member.pk, is_authenticated=False), request) is False
    from django.contrib.auth.models import AnonymousUser
    assert request_lifecycle.owner_may_cancel(AnonymousUser(), request) is False
    assert request_lifecycle.owner_may_cancel(None, request) is False
    request.status = HardwareRequest.Status.ISSUED
    assert request_lifecycle.owner_may_cancel(member, request) is False


# ---- expire_request ----------------------------------------------------------------------------------


def _accepted_with_deadline(slug, quantity=2, *features):
    space = space_with(slug, "loans.pickup_windows", *features)
    LoanReservationPolicy.objects.create(makerspace=space, pickup_window_hours=24)
    staff = make_member(f"{slug}-sm", space)
    product = make_product(space, available_quantity=quantity, total_quantity=quantity)
    request = workflow.accept_request(staff, submit(space, make_user(f"{slug}-m", access_status="active"), product, quantity))
    assert request.pickup_until is not None
    return space, product, request


def test_expire_request_audits_exact_meta_and_releases_the_units():
    space, product, request = _accepted_with_deadline("mp-expire-meta")
    assert stock(product) == (0, 2)
    done = request_lifecycle.expire_request(request, now=request.pickup_until + timedelta(minutes=1))
    assert done.status == HardwareRequest.Status.EXPIRED and done.closed_by_id is None and done.closed_at is not None
    assert stock(product) == (2, 0)
    assert audit_meta("request.expired", request) == {
        "pickup_until": request.pickup_until.isoformat(), "released_units": 2}
    assert AuditLog.objects.get(action="request.expired", target_id=str(request.pk)).actor_id is None


def test_expire_request_is_inclusive_at_the_deadline_and_refuses_each_other_case():
    space, product, request = _accepted_with_deadline("mp-expire-edge", 1)
    deadline = request.pickup_until
    # One second early, exactly on the deadline: the boundary is inclusive.
    assert request_lifecycle.expire_request(request, now=deadline - timedelta(seconds=1)) is None
    assert stock(product) == (0, 1)
    assert request_lifecycle.expire_request(request, now=deadline).status == HardwareRequest.Status.EXPIRED
    assert stock(product) == (1, 0)
    # Already expired: not accepted any more.
    assert request_lifecycle.expire_request(request, now=deadline + timedelta(days=1)) is None


def test_expire_request_refuses_a_non_accepted_row_even_with_a_past_deadline():
    space, product, request = _accepted_with_deadline("mp-expire-status", 1)
    HardwareRequest.objects.filter(pk=request.pk).update(status=HardwareRequest.Status.CANCELLED)
    assert request_lifecycle.expire_request(request, now=request.pickup_until + timedelta(days=1)) is None
    request.refresh_from_db()
    assert request.status == HardwareRequest.Status.CANCELLED
    assert stock(product) == (0, 1)


def test_expire_request_refuses_a_row_with_no_deadline():
    space, product, request = _accepted_with_deadline("mp-expire-nodeadline", 1)
    HardwareRequest.objects.filter(pk=request.pk).update(pickup_until=None)
    assert request_lifecycle.expire_request(request, now=timezone.now() + timedelta(days=30)) is None
    request.refresh_from_db()
    assert request.status == HardwareRequest.Status.ACCEPTED


def test_expire_request_refuses_when_the_pickup_window_switch_is_off():
    space, product, request = _accepted_with_deadline("mp-expire-off", 1)
    space.enabled_features = [name for name in space.enabled_features if name != "loans.pickup_windows"]
    space.save(update_fields=["enabled_features"])
    assert request_lifecycle.expire_request(request, now=request.pickup_until + timedelta(days=1)) is None
    request.refresh_from_db()
    assert request.status == HardwareRequest.Status.ACCEPTED
    assert stock(product) == (0, 1)


def test_expire_request_runs_the_source_gate_with_the_space_id():
    space, product, request = _accepted_with_deadline("mp-expire-gate", 1)
    with patch("apps.tenant_migration.gate_runtime.assert_write_allowed", side_effect=Boom) as gate:
        with pytest.raises(Boom):
            request_lifecycle.expire_request(request, now=request.pickup_until + timedelta(days=1))
    gate.assert_called_once_with(space.id)
    request.refresh_from_db()
    assert request.status == HardwareRequest.Status.ACCEPTED


def test_expire_request_notifies_the_requester_that_it_expired():
    space, product, request = _accepted_with_deadline("mp-expire-notify", 1)
    with patch("apps.hardware_requests.notifications_loans.notify_closed") as notify:
        request_lifecycle.expire_request(request, now=request.pickup_until + timedelta(days=1))
    notify.assert_called_once()
    row, event = notify.call_args.args
    assert row.pk == request.pk and event == "expired"


def test_expire_request_releases_a_claimed_waitlist_hold(django_capture_on_commit_callbacks):
    space, staff, product, entry, claimed = _claimed_waitlist_request("mp-expire-claim", django_capture_on_commit_callbacks)
    # Re-point the claim at an accepted, expiring request: accept it first (the claim converts to its reservation).
    LoanReservationPolicy.objects.create(makerspace=space, pickup_window_hours=24)
    space.enabled_features = sorted(set(space.enabled_features) | {"loans.pickup_windows"})
    space.save(update_fields=["enabled_features"])
    workflow.accept_request(staff, claimed)
    claimed.refresh_from_db()
    entry.refresh_from_db()
    assert entry.status == Entry.Status.FULFILLED
    assert stock(product) == (0, 1)
    request_lifecycle.expire_request(claimed, now=claimed.pickup_until + timedelta(minutes=1))
    assert stock(product) == (1, 0)


# ---- expire_due_requests -----------------------------------------------------------------------------


def _two_due(slug):
    space = space_with(slug, "loans.pickup_windows")
    LoanReservationPolicy.objects.create(makerspace=space, pickup_window_hours=24)
    staff = make_member(f"{slug}-sm", space)
    product = make_product(space, available_quantity=2, total_quantity=2)
    rows = [workflow.accept_request(staff, submit(space, make_user(f"{slug}-{n}", access_status="active"), product))
            for n in "ab"]
    return space, product, rows, timezone.now() + timedelta(hours=25)


@pytest.mark.parametrize("limit, expected", [(1, 1), (0, 1), (-5, 1), (2, 2), (200, 2)])
def test_the_sweep_is_bounded_by_its_limit_and_always_takes_at_least_one(limit, expected):
    space, product, rows, late = _two_due(f"mp-limit-{abs(limit)}")
    counts = request_lifecycle.expire_due_requests(now=late, limit=limit)
    assert counts == {"expired": expected, "skipped": 0, "lapsed": 0}
    assert HardwareRequest.objects.filter(status=HardwareRequest.Status.EXPIRED).count() == expected


def test_the_sweep_pages_the_pickup_rows_under_the_loan_pickups_label():
    from apps.operations.cloud_jobs import bounded
    space, product, rows, late = _two_due("mp-label")
    with patch("apps.operations.cloud_jobs.bounded.page", wraps=bounded.page) as page:
        request_lifecycle.expire_due_requests(now=late)
    assert [call.args[1] for call in page.call_args_list] == ["loan-pickups"]


def test_the_sweep_runs_each_row_under_the_loan_pickup_expiry_operation():
    from apps.tenant_migration import gate_runtime
    space, product, rows, late = _two_due("mp-operation")
    seen = []
    real = gate_runtime.fanout_tenant_write

    def spy(makerspace_id, *, operation, counts):
        seen.append((makerspace_id, operation))
        return real(makerspace_id, operation=operation, counts=counts)

    with patch("apps.tenant_migration.gate_runtime.fanout_tenant_write", spy):
        request_lifecycle.expire_due_requests(now=late)
    assert seen == [(space.id, "loan_pickup_expiry")] * 2


def test_a_read_only_space_still_expires_its_lapsed_pickups():
    space, product, rows, late = _two_due("mp-readonly")
    SpaceControlState.objects.update_or_create(
        makerspace=space, defaults={"read_only_at": timezone.now(), "read_only_source": "manual"})
    counts = request_lifecycle.expire_due_requests(now=late)
    assert counts == {"expired": 2, "skipped": 0, "lapsed": 0}
    assert InventoryProduct.objects.get(pk=product.pk).available_quantity == 2

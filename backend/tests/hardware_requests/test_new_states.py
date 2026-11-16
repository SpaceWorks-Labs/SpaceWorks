"""Inventory D1 / #77: cancelled and expired exits, each releasing the reservation."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.hardware_requests import workflow
from apps.hardware_requests.models import HardwareRequest, HardwareRequestItem
from apps.hardware_requests.models_loans import LoanReservationPolicy
from apps.hardware_requests.request_workflow import RequesterSnapshot
from apps.hardware_requests.workflow_errors import InvalidTransition, RequestValidationError
from tests.return_helpers import authenticated_client, make_member, make_product, make_space, make_user

pytestmark = pytest.mark.django_db


def space_with(slug, *features):
    space = make_space(slug)
    space.enabled_features = sorted(set(space.enabled_features or []) | {"loans.enabled", *features})
    space.save(update_fields=["enabled_features"])
    return space


def submit(space, member, product, quantity=1, **extra):
    snapshot = RequesterSnapshot(username=member.username, name="", email="", phone="")
    return workflow.submit_request(space, [{"product": product, "quantity": quantity}], "",
                                   requester_principal=member, contact_snapshot=snapshot,
                                   audit_actor=member, **extra)


def test_staff_cancel_releases_an_accepted_reservation():
    space = space_with("state-cancel")
    staff = make_member("state-cancel-sm", space)
    product = make_product(space, available_quantity=3, total_quantity=3)
    member = make_user("state-cancel-member", access_status="active")
    request = workflow.accept_request(staff, submit(space, member, product, 2))
    product.refresh_from_db()
    assert (product.available_quantity, product.reserved_quantity) == (1, 2)
    response = authenticated_client(staff).post(
        f"/api/v1/admin/makerspace/{space.pk}/requests/{request.pk}/cancel", {"reason": "duplicate"}, format="json")
    assert response.status_code == 200, response.content
    assert response.json()["status"] == "cancelled"
    product.refresh_from_db()
    assert (product.available_quantity, product.reserved_quantity) == (3, 0)
    log = AuditLog.objects.get(action="request.cancelled", target_id=str(request.pk))
    assert log.meta["released_units"] == 2 and log.meta["by_owner"] is False
    with pytest.raises(InvalidTransition):
        workflow.cancel_request(staff, request, by_owner=False)


def test_member_withdraw_needs_the_switch_and_ownership():
    space = space_with("state-withdraw")
    product = make_product(space)
    from apps.accounts.models import User
    member = make_member("state-withdraw-member", space, membership_role="custom", role=User.Role.REQUESTER)
    other = make_member("state-withdraw-other", space, membership_role="custom", role=User.Role.REQUESTER)
    request = submit(space, member, product)
    path = f"/api/v1/member/makerspaces/{space.pk}/requests/{request.pk}/withdraw"
    off = authenticated_client(member).post(path, {}, format="json")
    assert off.status_code == 404 and off.data["feature"] == "loans.withdrawals"  # switch off: typed SurfaceOff (#95, #183B)
    space.enabled_features = sorted(set(space.enabled_features) | {"loans.withdrawals"})
    space.save(update_fields=["enabled_features"])
    assert authenticated_client(other).post(path, {}, format="json").status_code == 404
    response = authenticated_client(member).post(path, {}, format="json")
    assert response.status_code == 200, response.content
    request.refresh_from_db()
    assert request.status == HardwareRequest.Status.CANCELLED and request.closed_by_id == member.pk


def test_pickup_deadline_expires_through_the_sweep_and_frees_stock():
    space = space_with("state-expire", "loans.pickup_windows")
    LoanReservationPolicy.objects.create(makerspace=space, pickup_window_hours=24)
    staff = make_member("state-expire-sm", space)
    product = make_product(space, available_quantity=1, total_quantity=1)
    member = make_user("state-expire-member", access_status="active")
    request = workflow.accept_request(staff, submit(space, member, product))
    assert request.pickup_until is not None
    assert workflow.expire_due_requests(now=timezone.now())["expired"] == 0
    counts = workflow.expire_due_requests(now=timezone.now() + timedelta(hours=25))
    assert counts["expired"] == 1
    request.refresh_from_db()
    product.refresh_from_db()
    assert request.status == HardwareRequest.Status.EXPIRED
    assert (product.available_quantity, product.reserved_quantity) == (1, 0)
    assert AuditLog.objects.filter(action="request.expired", target_id=str(request.pk)).exists()


def test_pickup_windows_off_never_expires():
    space = space_with("state-expire-off")
    LoanReservationPolicy.objects.create(makerspace=space, pickup_window_hours=1)
    staff = make_member("state-expire-off-sm", space)
    product = make_product(space)
    request = workflow.accept_request(staff, submit(space, make_user("seo-m", access_status="active"), product))
    assert request.pickup_until is None
    HardwareRequest.objects.filter(pk=request.pk).update(pickup_until=timezone.now() - timedelta(days=1))
    assert workflow.expire_due_requests(now=timezone.now())["expired"] == 0


def test_member_pickup_window_is_validated_and_kept():
    space = space_with("state-window", "loans.reservations", "loans.pickup_windows")
    product = make_product(space)
    member = make_user("state-window-member", access_status="active")
    start = timezone.now() + timedelta(days=2)
    request = submit(space, member, product, pickup_from=start, pickup_until=start + timedelta(hours=2))
    assert request.pickup_until == start + timedelta(hours=2)
    with pytest.raises(RequestValidationError):
        submit(space, member, product, pickup_from=timezone.now() + timedelta(days=400))
    with pytest.raises(RequestValidationError):
        submit(space, member, product, pickup_from=start, pickup_until=start - timedelta(hours=1))
    closed = space_with("state-window-off")
    with pytest.raises(RequestValidationError):
        submit(closed, member, make_product(closed), pickup_from=start)


def test_new_states_are_terminal_and_not_issuable():
    space = space_with("state-terminal")
    staff = make_member("state-terminal-sm", space)
    product = make_product(space)
    request = submit(space, make_user("state-terminal-m", access_status="active"), product)
    workflow.cancel_request(staff, request, by_owner=False)
    with pytest.raises(InvalidTransition):
        workflow.accept_request(staff, request)
    assert HardwareRequestItem.objects.filter(request=request).count() == 1

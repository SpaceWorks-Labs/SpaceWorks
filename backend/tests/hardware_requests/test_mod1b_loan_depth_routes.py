"""MOD-1B: loan depth routes - the reservation policy, the waitlist (member + staff) and the withdraw/cancel pair.

Every case asserts the exact status and typed code, the audit row, and that a refusal writes nothing. The member
withdraw and waitlist happy paths live in test_account_only_loan_depth.py; this file adds boundaries, tenancy, roles,
switches, idempotency and audit.
"""

import pytest

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.hardware_requests import workflow
from apps.hardware_requests.models import HardwareRequest
from apps.hardware_requests.models_loans import LoanReservationPolicy, LoanWaitlistEntry
from apps.hardware_requests.request_workflow import RequesterSnapshot
from tests.account_split.p1_helpers import staff
from tests.return_helpers import authenticated_client, make_product, make_space, make_user

pytestmark = pytest.mark.django_db


def space_with(slug, *features):
    space = make_space(slug)
    # Account-only borrowers: member accounts on, membership off (the identity rule the waitlist applies).
    space.enabled_modules = sorted((set(space.enabled_modules or []) | {"member_accounts", "request_workflow"}) - {"membership"})
    space.enabled_features = sorted(set(space.enabled_features or []) | {"loans.enabled", *features})
    space.save(update_fields=["enabled_modules", "enabled_features"])
    return space


def manager_of(space, name="mod1b-mgr", role="space_manager"):
    user, _ = staff(space, name, role=role, access_status=User.AccessStatus.ACTIVE)
    return user


def policy_url(space):
    return f"/api/v1/admin/makerspace/{space.pk}/loan-reservation-policy"


# --- reservation policy -------------------------------------------------------------

def test_the_policy_reads_its_defaults_without_creating_a_row():
    space = space_with("mod1b-pol-default")
    reply = authenticated_client(manager_of(space)).get(policy_url(space))
    assert reply.status_code == 200
    assert reply.data == {"pickup_window_hours": 0, "reservation_max_days_ahead": 30, "waitlist_offer_hours": 48}
    assert not LoanReservationPolicy.objects.exists()


@pytest.mark.parametrize("body", [
    {"pickup_window_hours": 0, "reservation_max_days_ahead": 1, "waitlist_offer_hours": 1},
    {"pickup_window_hours": 720, "reservation_max_days_ahead": 365, "waitlist_offer_hours": 336},
])
def test_every_policy_field_accepts_its_lower_and_upper_bound(body):
    space = space_with("mod1b-pol-ok-" + str(body["pickup_window_hours"]))
    reply = authenticated_client(manager_of(space)).put(policy_url(space), body, format="json")
    assert reply.status_code == 200, reply.data
    assert reply.data == body
    stored = LoanReservationPolicy.objects.get(makerspace=space)
    assert (stored.pickup_window_hours, stored.reservation_max_days_ahead, stored.waitlist_offer_hours) == tuple(body.values())


@pytest.mark.parametrize("body, field", [
    ({"pickup_window_hours": 721}, "pickup_window_hours"),
    ({"pickup_window_hours": -1}, "pickup_window_hours"),
    ({"reservation_max_days_ahead": 0}, "reservation_max_days_ahead"),
    ({"reservation_max_days_ahead": 366}, "reservation_max_days_ahead"),
    ({"waitlist_offer_hours": 0}, "waitlist_offer_hours"),
    ({"waitlist_offer_hours": 337}, "waitlist_offer_hours"),
    ({"waitlist_offer_hours": "abc"}, "waitlist_offer_hours"),
    ({"pickup_window_hours": 2.5}, "pickup_window_hours"),
])
def test_out_of_range_or_malformed_policy_values_are_refused_and_write_nothing(body, field):
    space = space_with("mod1b-pol-bad")
    reply = authenticated_client(manager_of(space)).put(policy_url(space), body, format="json")
    assert reply.status_code == 400 and field in reply.data, reply.data
    assert not LoanReservationPolicy.objects.exists()
    assert not AuditLog.objects.filter(action="settings.changed", makerspace=space).exists()


def test_a_change_is_audited_once_and_a_repeat_of_the_same_values_is_silent():
    space = space_with("mod1b-pol-audit")
    client = authenticated_client(manager_of(space))
    assert client.put(policy_url(space), {"pickup_window_hours": 24}, format="json").status_code == 200
    entry = AuditLog.objects.get(action="settings.changed", makerspace=space)
    assert (entry.meta["module"], entry.meta["key"], entry.meta["from"], entry.meta["to"]) == ("inventory", "pickup_window_hours", 0, 24)
    assert client.put(policy_url(space), {"pickup_window_hours": 24}, format="json").status_code == 200
    assert AuditLog.objects.filter(action="settings.changed", makerspace=space).count() == 1


def test_the_policy_is_refused_across_tenants_roles_and_when_signed_out():
    space, other = space_with("mod1b-pol-t1"), space_with("mod1b-pol-t2")
    outsider = manager_of(other, "mod1b-pol-outsider")
    assert authenticated_client(outsider).get(policy_url(space)).status_code == 404
    assert authenticated_client(outsider).put(policy_url(space), {"pickup_window_hours": 5}, format="json").status_code == 404
    events = manager_of(space, "mod1b-pol-events", role="event_manager")
    assert authenticated_client(events).get(policy_url(space)).status_code == 404
    from rest_framework.test import APIClient
    assert APIClient().get(policy_url(space)).status_code == 401
    assert not LoanReservationPolicy.objects.exists()


def test_the_request_workflow_is_a_core_module_so_the_policy_route_has_no_off_switch():
    from apps.makerspaces.module_install import ModuleInstallError, uninstall_module
    space = space_with("mod1b-pol-core")
    with pytest.raises(ModuleInstallError, match="core module"):
        uninstall_module(space, "request_workflow")
    assert authenticated_client(manager_of(space)).get(policy_url(space)).status_code == 200


# --- waitlist -----------------------------------------------------------------------

def waitlist_base(space):
    return f"/api/v1/member/makerspaces/{space.pk}/waitlist"


def out_product(space, **overrides):
    return make_product(space, available_quantity=0, total_quantity=1, issued_quantity=1, **overrides)


def test_joining_is_audited_once_and_a_second_join_or_a_double_click_adds_nothing():
    space = space_with("mod1b-wl-join", "loans.waitlist")
    product = out_product(space)
    borrower = make_user("mod1b-wl-borrower", access_status="active")
    client = authenticated_client(borrower)
    first = client.post(waitlist_base(space), {"product_id": product.pk}, format="json")
    assert first.status_code == 201 and (first.data["status"], first.data["position"]) == ("waiting", 1)
    again = client.post(waitlist_base(space), {"product_id": product.pk}, format="json")
    assert again.status_code == 400 and "already on the waitlist" in str(again.data)
    assert LoanWaitlistEntry.objects.count() == 1
    assert AuditLog.objects.filter(action="inventory.waitlist_joined").count() == 1
    left = client.post(f"{waitlist_base(space)}/{first.data['id']}/leave", {}, format="json")
    assert left.status_code == 200 and left.data["status"] == "cancelled"
    assert AuditLog.objects.filter(action="inventory.waitlist_left").count() == 1
    repeat = client.post(f"{waitlist_base(space)}/{first.data['id']}/leave", {}, format="json")
    assert repeat.status_code == 400 and "cannot be left" in str(repeat.data)
    assert AuditLog.objects.filter(action="inventory.waitlist_left").count() == 1


def test_positions_follow_the_order_people_joined():
    space = space_with("mod1b-wl-order", "loans.waitlist")
    product = out_product(space)
    people = [make_user(f"mod1b-wl-p{i}", access_status="active") for i in range(3)]
    rows = [authenticated_client(p).post(waitlist_base(space), {"product_id": product.pk}, format="json").data for p in people]
    assert [row["position"] for row in rows] == [1, 2, 3]


@pytest.mark.parametrize("body, why", [
    ({"product_id": 0}, "product_id"), ({"product_id": "x"}, "product_id"), ({}, "product_id"),
    ({"product_id": 1, "quantity": 0}, "quantity"), ({"product_id": 1, "quantity": 100}, "quantity"),
])
def test_waitlist_join_input_is_validated(body, why):
    space = space_with("mod1b-wl-input", "loans.waitlist")
    reply = authenticated_client(make_user("mod1b-wl-input-u", access_status="active")).post(waitlist_base(space), body, format="json")
    assert reply.status_code == 400 and why in reply.data
    assert not LoanWaitlistEntry.objects.exists()


def test_an_available_consumable_archived_private_or_foreign_item_cannot_be_waitlisted():
    space, other = space_with("mod1b-wl-items", "loans.waitlist"), space_with("mod1b-wl-items-2", "loans.waitlist")
    user = make_user("mod1b-wl-items-u", access_status="active")
    client = authenticated_client(user)
    available = make_product(space)
    reply = client.post(waitlist_base(space), {"product_id": available.pk}, format="json")
    assert reply.status_code == 400 and "available now" in str(reply.data)
    consumable = out_product(space, is_consumable=True, name="Glue")
    assert client.post(waitlist_base(space), {"product_id": consumable.pk}, format="json").status_code == 400
    for flags in ({"is_archived": True}, {"is_public": False}):
        hidden = out_product(space, name=f"hidden-{len(flags)}-{next(iter(flags))}", **flags)
        assert client.post(waitlist_base(space), {"product_id": hidden.pk}, format="json").status_code == 404
    foreign = out_product(other, name="elsewhere")
    assert client.post(waitlist_base(space), {"product_id": foreign.pk}, format="json").status_code == 404
    assert not LoanWaitlistEntry.objects.exists()


def test_the_waitlist_is_gated_by_its_capability_and_the_loans_master_with_typed_codes():
    space = space_with("mod1b-wl-off")  # loans.waitlist NOT enabled
    user = make_user("mod1b-wl-off-u", access_status="active")
    client = authenticated_client(user)
    product = out_product(space)
    for reply in (client.get(waitlist_base(space)), client.post(waitlist_base(space), {"product_id": product.pk}, format="json")):
        assert reply.status_code == 404 and reply.data["code"] == "feature_disabled" and reply.data["feature"] == "loans.waitlist"
    space.enabled_features = sorted({*space.enabled_features, "loans.waitlist"})
    space.save(update_fields=["enabled_features"])
    assert client.get(waitlist_base(space)).status_code == 200
    space.enabled_features = [key for key in space.enabled_features if key != "loans.enabled"]  # the Inventory master (decision 254)
    space.save(update_fields=["enabled_features"])
    off = client.get(waitlist_base(space))
    assert off.status_code == 404 and off.data["code"] == "module_disabled"  # the loans master answers as the workflow module (decision 254)


def test_a_restricted_account_cannot_join_and_nothing_is_written():
    space = space_with("mod1b-wl-restricted", "loans.waitlist")
    user = make_user("mod1b-wl-restricted-u", access_status="active")
    User.objects.filter(pk=user.pk).update(access_status=User.AccessStatus.RESTRICTED)
    user.refresh_from_db()
    reply = authenticated_client(user).post(waitlist_base(space), {"product_id": out_product(space).pk}, format="json")
    assert reply.status_code == 403, reply.data
    assert not LoanWaitlistEntry.objects.exists()


def test_staff_see_who_waits_in_order_filtered_by_product_and_never_across_tenants():
    space, other = space_with("mod1b-wl-staff", "loans.waitlist"), space_with("mod1b-wl-staff-2", "loans.waitlist")
    first, second = out_product(space, name="Scope"), out_product(space, name="Saw")
    for index, product in enumerate((first, first, second)):
        user = make_user(f"mod1b-wl-s{index}", access_status="active", display_name=f"Waiter {index}")
        authenticated_client(user).post(waitlist_base(space), {"product_id": product.pk}, format="json")
    url = f"/api/v1/admin/makerspace/{space.pk}/waitlist"
    manager = authenticated_client(manager_of(space, "mod1b-wl-staff-m"))
    everyone = manager.get(url)
    assert everyone.status_code == 200 and sorted(r["member_name"] for r in everyone.data) == ["Waiter 0", "Waiter 1", "Waiter 2"]
    only_first = manager.get(url, {"product": first.pk})
    assert sorted(r["member_name"] for r in only_first.data) == ["Waiter 0", "Waiter 1"]
    assert manager.get(url, {"product": "abc"}).data == []
    outsider = authenticated_client(manager_of(other, "mod1b-wl-staff-out"))
    assert outsider.get(url).status_code == 404
    plain = authenticated_client(make_user("mod1b-wl-plain", access_status="active"))
    assert plain.get(url).status_code == 404  # no staff authority here: the workflow scope hides the route


# --- cancel / withdraw --------------------------------------------------------------

def submitted(space, user, product):
    snapshot = RequesterSnapshot(username=user.username, name="", email="", phone="")
    return workflow.submit_request(space, [{"product": product, "quantity": 1}], "", requester_principal=user,
                                   contact_snapshot=snapshot, audit_actor=user)


def test_staff_cancel_closes_a_pending_request_once_audits_it_and_refuses_a_second_cancel():
    space = space_with("mod1b-cancel", "loans.withdrawals")
    owner = make_user("mod1b-cancel-owner", access_status="active")
    request = submitted(space, owner, make_product(space))
    client = authenticated_client(manager_of(space, "mod1b-cancel-m"))
    url = f"/api/v1/admin/makerspace/{space.pk}/requests/{request.pk}/cancel"
    done = client.post(url, {"reason": "Out for repair"}, format="json")
    assert done.status_code == 200 and done.data["status"] == HardwareRequest.Status.CANCELLED
    again = client.post(url, {}, format="json")
    assert again.status_code == 409, again.data
    long = client.post(url, {"reason": "x" * 501}, format="json")
    assert long.status_code == 400 and "reason" in long.data


def test_cancel_and_withdraw_never_cross_tenants():
    space, other = space_with("mod1b-cancel-x", "loans.withdrawals"), space_with("mod1b-cancel-y", "loans.withdrawals")
    owner = make_user("mod1b-cancel-x-owner", access_status="active")
    request = submitted(space, owner, make_product(space))
    outsider = authenticated_client(manager_of(other, "mod1b-cancel-out"))
    assert outsider.post(f"/api/v1/admin/makerspace/{other.pk}/requests/{request.pk}/cancel", {}, format="json").status_code == 404
    assert outsider.post(f"/api/v1/admin/makerspace/{space.pk}/requests/{request.pk}/cancel", {}, format="json").status_code == 404
    stranger = authenticated_client(make_user("mod1b-cancel-stranger", access_status="active"))
    assert stranger.post(f"/api/v1/member/makerspaces/{space.pk}/requests/{request.pk}/withdraw", {}, format="json").status_code == 404
    assert HardwareRequest.objects.get(pk=request.pk).status == HardwareRequest.Status.PENDING_APPROVAL

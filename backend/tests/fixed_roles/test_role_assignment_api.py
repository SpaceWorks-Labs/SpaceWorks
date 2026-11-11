"""Both staff role endpoints replace a complete, non-escalating set."""
import pytest
from django.urls import reverse

from apps.accounts import rbac
from apps.audit.models import AuditLog
from apps.machines.models import MachineType
from apps.machines.models_membership_scope import MembershipMachineTypeScope
from apps.makerspaces.models import MakerspaceRole
from tests.fixed_roles.helpers import assign_builtin_roles
from tests.return_helpers import authenticated_client, make_space, make_user

pytestmark = pytest.mark.django_db


@pytest.fixture
def lab():
    space = make_space("assignment-api")
    actor = make_user("assignment-boss", access_status="active", account_kind="staff", staff_makerspace=space)
    assign_builtin_roles(actor, space, "space_manager")
    target = make_user("assignment-target", access_status="active", account_kind="staff", staff_makerspace=space)
    membership = assign_builtin_roles(target, space, "event_manager")
    roles = {row.slug: row for row in MakerspaceRole.objects.filter(makerspace=space)}
    return space, actor, membership, roles


def endpoint(space, membership, route):
    if route == "admin-membership-role-m2":
        return reverse(route, kwargs={"pk": membership.pk})
    return reverse(route, kwargs={"makerspace_id": space.pk, "membership_id": membership.pk})


@pytest.fixture(params=["admin-membership-role-assign", "admin-membership-role-m2"])
def url(lab, request):
    space, _, membership, _ = lab
    return endpoint(space, membership, request.param)


def test_complete_set_success_payload_and_audit(lab, url):
    space, actor, membership, roles = lab
    ids = [roles["booking_manager"].pk, roles["event_manager"].pk]
    response = authenticated_client(actor).patch(url, {"role_ids": ids}, format="json")
    assert response.status_code == 200, response.data
    assert response.data["role_ids"] == list(reversed(ids))
    assert {row["slug"] for row in response.data["roles"]} == {"event_manager", "booking_manager"}
    assert rbac.can(membership.user, rbac.Action.MANAGE_BOOKINGS, space.pk)
    audit = AuditLog.objects.get(action="staff.roles_changed", makerspace=space)
    assert audit.meta["before"] == ["event_manager"]
    assert audit.meta["after"] == ["event_manager", "booking_manager"]
    assert audit.meta["membership_id"] == membership.pk


def test_single_role_compatibility_replaces_additional_roles(lab, url):
    space, actor, membership, roles = lab
    assign_builtin_roles(membership.user, space, "event_manager", "booking_manager")
    response = authenticated_client(actor).patch(url, {"role_id": roles["handover"].pk}, format="json")
    assert response.status_code == 200, response.data
    assert response.data["role_ids"] == [roles["handover"].pk]
    assert not membership.additional_roles.exists()


@pytest.mark.parametrize("kind", ["both", "none", "empty", "space_manager", "member", "foreign"])
def test_invalid_sets_do_not_change_membership(lab, url, kind):
    space, actor, membership, roles = lab
    payload = {"role_ids": [roles["event_manager"].pk]}
    if kind == "both":
        payload["role_id"] = roles["event_manager"].pk
    elif kind == "none":
        payload = {}
    elif kind == "empty":
        payload = {"role_ids": []}
    elif kind in ("space_manager", "member"):
        payload["role_ids"].append(roles[kind].pk)
    else:
        other = make_space("assignment-foreign")
        payload = {"role_ids": [MakerspaceRole.objects.get(makerspace=other, slug="event_manager").pk]}
    response = authenticated_client(actor).patch(url, payload, format="json")
    assert response.status_code == (404 if kind == "foreign" else 400), response.data
    membership.refresh_from_db()
    assert membership.assigned_role_id == roles["event_manager"].pk
    assert not membership.additional_roles.exists()
    assert not AuditLog.objects.filter(action="staff.roles_changed").exists()


def test_only_superadmin_can_grant_space_manager(lab, url):
    _, actor, _, roles = lab
    payload = {"role_ids": [roles["space_manager"].pk]}
    assert authenticated_client(actor).patch(url, payload, format="json").status_code == 403
    root = make_user("assignment-root", role="superadmin", access_status="active")
    assert authenticated_client(root).patch(url, payload, format="json").status_code == 200


def test_actor_without_manage_makerspace_cannot_grant_staff(lab, url):
    space, actor, _, roles = lab
    assign_builtin_roles(actor, space, "inventory_manager")
    response = authenticated_client(actor).patch(url, {"role_ids": [roles["booking_manager"].pk]}, format="json")
    assert response.status_code == 403


def test_removing_machine_manager_clears_only_that_persons_type_links(lab, url):
    space, actor, membership, roles = lab
    kind = MachineType.objects.create(makerspace=space, slug="assign-laser", name="Laser")
    assign_builtin_roles(membership.user, space, "machine_manager", "event_manager", machine_types=[kind])
    peer = make_user("assignment-peer", access_status="active", account_kind="staff", staff_makerspace=space)
    peer_membership = assign_builtin_roles(peer, space, "machine_manager", machine_types=[kind])
    response = authenticated_client(actor).patch(url, {"role_ids": [roles["event_manager"].pk]}, format="json")
    assert response.status_code == 200, response.data
    assert not MembershipMachineTypeScope.objects.filter(membership=membership).exists()
    assert MembershipMachineTypeScope.objects.filter(membership=peer_membership).exists()


def test_revoke_refuses_legacy_reattach_and_requires_explicit_reactivation(lab):
    space, actor, membership, roles = lab
    kind = MachineType.objects.create(makerspace=space, slug="lifecycle-laser", name="Laser")
    assign_builtin_roles(membership.user, space, "machine_manager", "event_manager", machine_types=[kind])
    client = authenticated_client(actor)
    revoked = client.post(reverse("admin-membership-revoke-m2", kwargs={"pk": membership.pk}),
                          {"reason": "Staff lifecycle"}, format="json")
    assert revoked.status_code == 200, revoked.data
    membership.refresh_from_db(); membership.user.refresh_from_db()
    assert membership.status == "revoked" and not membership.user.is_active
    response = client.post(reverse("admin-membership-list-create", kwargs={"makerspace_id": space.pk}),
        {"username": membership.user.username, "role_ids": [roles["machine_manager"].pk]}, format="json")
    assert response.status_code == 400
    membership.refresh_from_db()
    assert membership.status == "revoked"
    restored = client.post(f"/api/v1/admin/makerspaces/{space.pk}/staff-accounts/{membership.user_id}/reactivate/",
                           {}, format="json")
    assert restored.status_code == 200, restored.data
    membership.user.refresh_from_db()
    assert membership.user.is_active and not membership.user.has_usable_password()


def test_assignment_rolls_back_when_audit_cannot_be_written(lab, url, monkeypatch):
    space, actor, membership, roles = lab
    from apps.makerspaces import role_assignments

    def unavailable(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(role_assignments.audit, "record", unavailable)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        authenticated_client(actor).patch(url, {"role_ids": [roles["booking_manager"].pk]}, format="json")
    membership.refresh_from_db()
    assert membership.assigned_role_id == roles["event_manager"].pk
    assert not membership.additional_roles.exists()

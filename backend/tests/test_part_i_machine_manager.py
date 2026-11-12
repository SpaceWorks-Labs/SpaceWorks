"""Part I — Machine Manager role + Space-Manager-delegated role assignment.

Focus: the non-escalation guards. A Space Manager may assign/list/revoke only the four
delegable roles (machine/print/inventory manager, guest admin) within their own makerspace,
and may NEVER create, overwrite, or revoke a Space Manager membership. Only a superadmin can.
"""
import pytest

from apps.accounts import rbac
from apps.accounts.models import User
from apps.makerspaces.models import MakerspaceMembership
from tests.return_helpers import (
    authenticated_client,
    make_member,
    make_space,
    make_user,
)

pytestmark = pytest.mark.django_db


def _membership(user, makerspace):
    return MakerspaceMembership.staff_tracks.get(user=user, makerspace=makerspace)


def test_machine_manager_role_implies_manage_printing():
    makerspace = make_space("mm-rbac")
    machine_manager = make_member(
        "mm-rbac-user",
        makerspace,
        membership_role=MakerspaceMembership.Role.MACHINE_MANAGER,
        role=User.Role.REQUESTER,
    )

    assert rbac.can(machine_manager, rbac.Action.MANAGE_MACHINES, makerspace.id)
    assert rbac.can(machine_manager, rbac.Action.MANAGE_PRINTING, makerspace.id)
    assert rbac.effective_actions(machine_manager, makerspace.id) == {
        rbac.Action.MANAGE_MACHINES,
        rbac.Action.MANAGE_PRINTING,
        # Handing a finished job to its requester is part of running the machines, so
        # MANAGE_MACHINES implies it and a Machine Manager needs no separate grant.
        rbac.Action.COLLECT_SERVICE_REQUEST,
    }
    # Other privileged actions remain denied.
    for action in (
        rbac.Action.MANAGE_MAKERSPACE,
        rbac.Action.EDIT_INVENTORY,
        rbac.Action.MANAGE_EVENTS,
        rbac.Action.ISSUE_REQUEST,
        rbac.Action.MANAGE_STAFF,
    ):
        assert not rbac.can(machine_manager, action, makerspace.id), action


@pytest.mark.skip(reason="U-A1/U-B: the /admin/makerspaces/<id>/staff-accounts/ routes are retired (404); staff roles are staff-track memberships on the person's one account")
def test_space_manager_can_create_separate_machine_manager_in_own_makerspace():
    makerspace = make_space("mm-assign")
    manager = make_member("mm-assign-admin", makerspace)
    response = authenticated_client(manager).post(
        f"/api/v1/admin/makerspaces/{makerspace.pk}/staff-accounts/",
        {"display_name": "Delegated machine manager", "username": "delegated-machine-manager",
         "roles": ["machine_manager"]}, format="json")
    assert response.status_code == 201
    account = User.objects.get(pk=response.data["account"]["id"])
    assert account.account_kind == "staff" and account.staff_makerspace_id == makerspace.pk
    assert _membership(account, makerspace).role == "machine_manager"
    assert account.role == User.Role.REQUESTER


@pytest.mark.skip(reason="U-A1/U-B: the /admin/makerspaces/<id>/staff-accounts/ routes are retired (404); staff roles are staff-track memberships on the person's one account")
def test_space_manager_cannot_create_space_manager():
    makerspace = make_space("mm-no-escalate")
    manager = make_member("mm-no-escalate-admin", makerspace)
    response = authenticated_client(manager).post(
        f"/api/v1/admin/makerspaces/{makerspace.pk}/staff-accounts/",
        {"display_name": "Peer", "username": "would-be-peer", "roles": ["space_manager"]}, format="json")
    assert response.status_code == 403
    assert not User.objects.filter(username="would-be-peer.mm-no-escalate").exists()


@pytest.mark.skip(reason="U-A1/U-B: the /admin/makerspaces/<id>/staff-accounts/ routes are retired (404); staff roles are staff-track memberships on the person's one account")
def test_space_manager_cannot_overwrite_existing_space_manager_membership():
    makerspace = make_space("mm-no-overwrite")
    manager = make_member("mm-no-overwrite-admin", makerspace)
    peer = make_member("mm-no-overwrite-peer", makerspace)
    response = authenticated_client(manager).patch(
        f"/api/v1/admin/makerspaces/{makerspace.pk}/staff-accounts/{peer.pk}/",
        {"roles": ["inventory_manager"]}, format="json")
    assert response.status_code == 403
    assert _membership(peer, makerspace).role == MakerspaceMembership.Role.SPACE_MANAGER


@pytest.mark.skip(reason="U-A1/U-B: the /admin/makerspaces/<id>/staff-accounts/ routes are retired (404); staff roles are staff-track memberships on the person's one account")
def test_superadmin_can_change_manager_roles_through_lifecycle_only():
    makerspace = make_space("mm-super-overwrite")
    root = make_user("mm-super-overwrite-admin", role=User.Role.SUPERADMIN, access_status="active")
    peer = make_member("mm-super-overwrite-peer", makerspace)
    make_member("mm-super-remaining-manager", makerspace)
    response = authenticated_client(root).patch(
        f"/api/v1/admin/makerspaces/{makerspace.pk}/staff-accounts/{peer.pk}/",
        {"roles": ["inventory_manager"]}, format="json")
    assert response.status_code == 200
    assert _membership(peer, makerspace).role == MakerspaceMembership.Role.INVENTORY_MANAGER


def test_space_manager_can_revoke_delegable_membership():
    makerspace = make_space("mm-revoke")
    space_manager = make_member("mm-revoke-admin", makerspace)
    target = make_member(
        "mm-revoke-target",
        makerspace,
        membership_role=MakerspaceMembership.Role.MACHINE_MANAGER,
        role=User.Role.REQUESTER,
    )
    membership_id = _membership(target, makerspace).id

    response = authenticated_client(space_manager).delete(
        f"/api/v1/admin/memberships/{membership_id}"
    )

    assert response.status_code == 204
    assert MakerspaceMembership.staff_tracks.get(pk=membership_id).status == "revoked"
    target.refresh_from_db()
    # U-A1: revoking a staff role removes the row only; the person's one account stays active.
    assert target.is_active
    # The account itself is not deleted.
    assert User.objects.filter(pk=target.id).exists()


def test_space_manager_cannot_revoke_space_manager_membership():
    makerspace = make_space("mm-revoke-sm")
    space_manager = make_member("mm-revoke-sm-admin", makerspace)
    peer = make_member("mm-revoke-sm-peer", makerspace)
    membership_id = _membership(peer, makerspace).id

    response = authenticated_client(space_manager).delete(
        f"/api/v1/admin/memberships/{membership_id}"
    )

    assert response.status_code == 403
    assert MakerspaceMembership.staff_tracks.filter(pk=membership_id).exists()


def test_space_manager_cannot_revoke_cross_tenant_membership():
    own = make_space("mm-revoke-own")
    other = make_space("mm-revoke-other")
    space_manager = make_member("mm-revoke-own-admin", own)
    outsider = make_member(
        "mm-revoke-other-target",
        other,
        membership_role=MakerspaceMembership.Role.MACHINE_MANAGER,
        role=User.Role.REQUESTER,
    )
    membership_id = _membership(outsider, other).id

    response = authenticated_client(space_manager).delete(
        f"/api/v1/admin/memberships/{membership_id}"
    )

    # Out-of-scope existence is hidden as 404, not 403.
    assert response.status_code == 404
    assert MakerspaceMembership.staff_tracks.filter(pk=membership_id).exists()


def test_superadmin_can_revoke_space_manager_membership():
    makerspace = make_space("mm-super-revoke")
    superadmin = make_user(
        "mm-super-revoke-admin",
        role=User.Role.SUPERADMIN,
        access_status=User.AccessStatus.ACTIVE,
    )
    # A second active Space Manager keeps the space from losing its last one: the lifecycle
    # service refuses to remove the last active manager (409), so the revoke needs a successor.
    make_member("mm-super-revoke-successor", makerspace)
    peer = make_member("mm-super-revoke-peer", makerspace)
    membership_id = _membership(peer, makerspace).id

    response = authenticated_client(superadmin).delete(
        f"/api/v1/admin/memberships/{membership_id}"
    )

    assert response.status_code == 204
    # Revocation ends the access but keeps the staff row for the audit trail.
    assert MakerspaceMembership.staff_tracks.get(pk=membership_id).status == "revoked"


def test_machine_manager_sees_own_makerspace_in_switcher_with_modules():
    # Regression: a machine_manager-only account must resolve its tenant via the switcher
    # (MANAGE_MACHINES in scope) and receive enabled_modules so the console keeps the
    # Machines tab.
    makerspace = make_space("mm-switcher")
    machine_manager = make_member(
        "mm-switcher-user",
        makerspace,
        membership_role=MakerspaceMembership.Role.MACHINE_MANAGER,
        role=User.Role.REQUESTER,
    )

    response = authenticated_client(machine_manager).get("/api/v1/admin/makerspaces")

    assert response.status_code == 200
    rows = response.data["results"] if isinstance(response.data, dict) else response.data
    assert [row["id"] for row in rows] == [makerspace.id]
    # Slim switcher row must carry module flags for tab gating.
    assert "enabled_modules" in rows[0]


def test_space_manager_can_list_machine_managers_in_scope():
    makerspace = make_space("mm-list")
    space_manager = make_member("mm-list-admin", makerspace)
    make_member(
        "mm-list-target",
        makerspace,
        membership_role=MakerspaceMembership.Role.MACHINE_MANAGER,
        role=User.Role.REQUESTER,
    )

    response = authenticated_client(space_manager).get(
        "/api/v1/admin/users/machine-managers"
    )

    assert response.status_code == 200
    rows = response.data["results"] if isinstance(response.data, dict) else response.data
    assert {row["role"] for row in rows} == {MakerspaceMembership.Role.MACHINE_MANAGER}
    assert {row["user"]["username"] for row in rows} == {"mm-list-target"}

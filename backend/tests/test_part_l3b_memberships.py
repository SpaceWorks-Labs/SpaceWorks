from tests.fixed_roles.helpers import roles_for_actions
import pytest
from django.urls import reverse

from apps.accounts import rbac
from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.makerspaces import limits
from apps.makerspaces.models import MakerspaceMembership, MakerspaceRole
from tests.return_helpers import authenticated_client, make_member, make_space, make_user


pytestmark = pytest.mark.django_db


def seeded(makerspace, legacy_role):
    return MakerspaceRole.objects.get(
        makerspace=makerspace, legacy_role=legacy_role
    )


def root(username):
    return make_user(
        username,
        role=User.Role.SUPERADMIN,
        access_status=User.AccessStatus.ACTIVE,
    )


def membership_url(makerspace):
    return reverse(
        "admin-membership-list-create", kwargs={"makerspace_id": makerspace.id}
    )


def assign_url(makerspace, membership):
    return reverse(
        "admin-membership-role-assign",
        kwargs={"makerspace_id": makerspace.id, "membership_id": membership.id},
    )


def test_generic_create_refuses_staff_roles_and_leaves_no_account():
    makerspace, actor = make_space("l3b-create"), root("l3b-create-root")
    api = authenticated_client(actor)
    for role in [seeded(makerspace, "inventory_manager"), seeded(makerspace, "machine_manager")]:
        response = api.post(membership_url(makerspace),
            {"username": "l3b-old-writer", "role_id": role.pk}, format="json")
        assert response.status_code == 400
    assert not User.objects.filter(username="l3b-old-writer").exists()
    assert not MakerspaceMembership.objects.filter(makerspace=makerspace).exists()


def test_membership_scope_ordering_and_assignment_audit():
    makerspace, foreign = make_space("l3b-scope"), make_space("l3b-foreign")
    actor = root("l3b-scope-root")
    target = make_member("l3b-scope-target", makerspace,
                         membership_role="handover", role=User.Role.REQUESTER)
    membership = MakerspaceMembership.staff_tracks.get(user=target, makerspace=makerspace)
    api = authenticated_client(actor)
    custom = roles_for_actions(makerspace, [rbac.Action.VIEW_INVENTORY])[0]
    foreign_role = roles_for_actions(foreign, [])[0]

    assert api.post(
        membership_url(makerspace),
        {"username": "l3b-foreign-role", "role_id": foreign_role.id},
        format="json",
    ).status_code == 404
    foreign_membership = MakerspaceMembership.objects.create(
        user=make_user("l3b-foreign-member", access_status=User.AccessStatus.ACTIVE),
        makerspace=foreign, role="custom", assigned_role=foreign_role,
    )
    assert api.patch(
        assign_url(makerspace, foreign_membership), {"role_id": custom.id}, format="json"
    ).status_code == 404

    # One account per person: the legacy membership route reaches COMMUNITY rows only; a
    # staff-track row is managed by the staff-roles API (U-B), so it is not found here.
    before = membership.assigned_role_id
    patched = api.patch(
        assign_url(makerspace, membership), {"role_id": custom.id}, format="json"
    )
    assert patched.status_code == 404
    membership.refresh_from_db()
    assert membership.assigned_role_id == before and membership.track == "staff"
    assert not AuditLog.objects.filter(
        action="staff.roles_changed", makerspace=makerspace, target_id=str(target.id)
    ).exists()

    outsider = authenticated_client(
        make_user("l3b-outsider", access_status=User.AccessStatus.ACTIVE)
    )
    assert outsider.get(membership_url(makerspace)).status_code == 404
    non_manager = make_member(
        "l3b-non-manager", makerspace,
        membership_role=MakerspaceMembership.Role.PRINT_MANAGER,
        role=User.Role.REQUESTER,
    )
    assert authenticated_client(non_manager).get(membership_url(makerspace)).status_code == 403
    makerspace.archived_at = "2024-01-01T00:00:00Z"
    makerspace.save(update_fields=["archived_at"])
    assert api.get(membership_url(makerspace)).status_code == 404


def test_dynamic_assignment_and_revoke_authority():
    makerspace = make_space("l3b-authority")
    manager = make_member("l3b-manager", makerspace)
    target = make_user("l3b-target", access_status=User.AccessStatus.ACTIVE)
    protected = MakerspaceMembership.staff_tracks.create(
        user=target, track="staff",
        makerspace=makerspace,
        role=MakerspaceMembership.Role.SPACE_MANAGER,
        assigned_role=seeded(makerspace, MakerspaceMembership.Role.SPACE_MANAGER),
    )
    governance = roles_for_actions(makerspace, [rbac.Action.MANAGE_MAKERSPACE])[0]
    manager_membership = MakerspaceMembership.staff_tracks.get(
        makerspace=makerspace, user=manager
    )
    manager_membership.assigned_role = seeded(
        makerspace, MakerspaceMembership.Role.SPACE_MANAGER
    )
    manager_membership.save(update_fields=["assigned_role"])
    events = roles_for_actions(makerspace, [rbac.Action.MANAGE_EVENTS])[0]
    manager_api = authenticated_client(manager)
    assert manager_api.post(
        membership_url(makerspace),
        {"username": "l3b-escalate", "role_id": governance.id},
        format="json",
    ).status_code == 400
    assert manager_api.post(
        membership_url(makerspace),
        {"username": "l3b-event-delegate", "role_id": events.id},
        format="json",
    ).status_code == 400
    # Staff-track rows are invisible to the legacy membership routes (staff roles are U-B's
    # staff-roles API, Space Manager changes superadmin-only there); nothing changes here.
    assert manager_api.patch(
        assign_url(makerspace, protected), {"role_id": seeded(makerspace, MakerspaceMembership.Role.MACHINE_MANAGER).id},
        format="json",
    ).status_code == 404
    assert manager_api.delete(
        reverse("admin-membership-revoke", kwargs={"pk": protected.id})
    ).status_code in (403, 404)

    root_api = authenticated_client(root("l3b-root"))
    assert root_api.patch(
        assign_url(makerspace, protected), {"role_id": governance.id}, format="json"
    ).status_code == 404
    delegated = MakerspaceMembership.staff_tracks.create(
        user=make_user("l3b-delegated", access_status=User.AccessStatus.ACTIVE), track="staff",
        makerspace=makerspace,
        role=MakerspaceMembership.Role.MACHINE_MANAGER,
        assigned_role=seeded(makerspace, MakerspaceMembership.Role.MACHINE_MANAGER),
    )
    # A Space Manager may revoke a delegable staff row (never a peer manager); the revoke
    # removes the staff-track row only and the person's one account stays active (U-A1).
    assert manager_api.delete(
        reverse("admin-membership-revoke", kwargs={"pk": delegated.id})
    ).status_code == 204
    for row in (delegated, protected):
        row.refresh_from_db()
        row.user.refresh_from_db()
        assert row.user.is_active
    assert delegated.status == "revoked" and protected.status == "active"


def test_legacy_create_is_refused():
    makerspace, actor = make_space("l3b-legacy"), root("l3b-legacy-root")
    api = authenticated_client(actor)
    refused = api.post(reverse("admin-users-space-managers"),
        {"username": "l3b-legacy-manager", "makerspace_id": makerspace.pk, "role": "space_manager"}, format="json")
    assert refused.status_code == 400
    assert not User.objects.filter(username="l3b-legacy-manager").exists()


@pytest.mark.skip(reason="U-A1/U-B: the /admin/makerspaces/<id>/staff-accounts/ create route is retired (404); the staff quota now applies to staff-track grants, not new accounts")
def test_new_staff_creation_enforces_quota(monkeypatch):
    makerspace, actor = make_space("l3b-legacy"), root("l3b-legacy-root")
    api = authenticated_client(actor)
    capped = make_space("l3b-cap")
    capped.resource_limit_overrides = {"staff": 0}
    capped.save(update_fields=["resource_limit_overrides"])
    monkeypatch.setattr(limits, "is_self_host", lambda: False)
    rejected = api.post(f"/api/v1/admin/makerspaces/{capped.pk}/staff-accounts/",
        {"display_name": "No orphan", "username": "l3b-no-orphan", "roles": ["machine_manager"]}, format="json")
    assert rejected.status_code == 400, rejected.data
    assert rejected.data["limit"].code == "limit_reached"
    assert not User.objects.filter(staff_makerspace=capped).exists()
    assert not MakerspaceMembership.objects.filter(makerspace=capped).exists()


def test_attaching_existing_account_preserves_global_role():
    # Staff duties require a separate tenant principal. Refusing the attachment
    # must never demote the platform principal or create a tenant membership.
    makerspace = make_space("l3b-global-role")
    manager = make_member("l3b-gr-manager", makerspace)
    manager_membership = MakerspaceMembership.staff_tracks.get(makerspace=makerspace, user=manager)
    manager_membership.assigned_role = seeded(
        makerspace, MakerspaceMembership.Role.SPACE_MANAGER
    )
    manager_membership.save(update_fields=["assigned_role"])
    victim = make_user(
        "l3b-hidden-superadmin",
        role=User.Role.SUPERADMIN,
        access_status=User.AccessStatus.ACTIVE,
    )
    readers = roles_for_actions(makerspace, [rbac.Action.VIEW_INVENTORY])[0]
    resp = authenticated_client(manager).post(
        membership_url(makerspace),
        {"username": victim.username, "role_id": readers.id},
        format="json",
    )
    assert resp.status_code == 400
    victim.refresh_from_db()
    assert victim.role == User.Role.SUPERADMIN
    assert victim.account_kind == "platform" and victim.is_superuser
    assert not victim.makerspace_memberships.exists()


def test_oversized_account_field_is_a_clean_400():
    # P2: an oversized username must be a validation error, not a DB DataError -> 500.
    makerspace, actor = make_space("l3b-oversize"), root("l3b-oversize-root")
    readers = roles_for_actions(makerspace, [rbac.Action.VIEW_INVENTORY])[0]
    resp = authenticated_client(actor).post(
        membership_url(makerspace),
        {"username": "x" * 151, "role_id": readers.id},
        format="json",
    )
    assert resp.status_code == 400
    assert not User.objects.filter(username="x" * 151).exists()

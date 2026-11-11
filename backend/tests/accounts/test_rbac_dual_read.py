import pytest
from django.utils import timezone
from django.db import IntegrityError, connection, transaction

from apps.accounts import rbac
from apps.accounts.models import User
from apps.makerspaces.models import Makerspace, MakerspaceMembership, MakerspaceRole


pytestmark = pytest.mark.django_db


def make_user(username, makerspace=None, **kwargs):
    if kwargs.get("is_superuser") or kwargs.get("role") == "superadmin":
        kwargs.setdefault("account_kind", "platform")
        kwargs.setdefault("is_superuser", True)
    elif makerspace is not None:
        kwargs.update(account_kind="staff", staff_makerspace=makerspace)
    creator = User.objects.create_superuser if kwargs.get("is_superuser") else User.objects.create_user
    return creator(
        username=username,
        email=f"{username}@example.com",
        password="password",
        **kwargs,
    )


def make_makerspace(slug, **kwargs):
    return Makerspace.objects.create(name=slug, slug=slug, **kwargs)


def seeded_role(makerspace, legacy_role):
    # Print Manager survives only as a null-FK legacy compatibility value.
    return MakerspaceRole.objects.filter(makerspace=makerspace, legacy_role=legacy_role).first()

def custom_role(makerspace, slug, actions):
    """Compatibility name for older importers; returns a real built-in role."""
    from tests.fixed_roles.helpers import roles_for_actions
    return roles_for_actions(makerspace, actions)[0]


def test_action_registries_contain_the_frozen_action_vocabulary():
    # 19 since collect_service_request split job handover out of manage_machines;
    # 21 with the member-card pair (scan_member_cards, manage_member_cards);
    # 22 with manage_devices (phase 7a); 25 with member and finance delegation;
    # 26 with record_reimbursement_payout (event reimbursements).
    assert len(rbac.ALL_ACTIONS) == 26
    assert rbac.ROLE_FORBIDDEN_ACTIONS == {
        rbac.Action.TRANSFER_STOCK,
        rbac.Action.MANAGE_STAFF,
    }
    assert rbac.ROLE_GRANTABLE_ACTIONS == (
        rbac.ALL_ACTIONS - rbac.ROLE_FORBIDDEN_ACTIONS
    )


def test_assigned_roles_match_the_frozen_legacy_matrix():
    makerspace = make_makerspace("dual-read-assigned")
    memberships = {}
    for index, legacy_role in enumerate(rbac._MEMBERSHIP_ROLE_ACTIONS):
        if legacy_role == "print_manager":
            continue  # There is no current built-in for this legacy spelling.
        membership = MakerspaceMembership.objects.create(
            makerspace=makerspace,
            user=make_user(f"assigned-default-{index}", makerspace=makerspace),
            role=legacy_role,
            assigned_role=seeded_role(makerspace, legacy_role),
        )
        memberships[legacy_role] = membership

    for legacy_role, membership in memberships.items():
        expected = rbac.expand_implied_actions(set(rbac._MEMBERSHIP_ROLE_ACTIONS[legacy_role]))
        assert rbac.actions_for_membership(membership) == expected
        for action in rbac.ALL_ACTIONS:
            assert rbac.can(membership.user, action, makerspace.id) == (action in expected)


def test_null_assigned_role_fails_closed_for_every_legacy_label():
    makerspace = make_makerspace("dual-read-fallback")
    for index, legacy_role in enumerate(rbac._MEMBERSHIP_ROLE_ACTIONS):
        primary = seeded_role(makerspace, "machine_manager" if legacy_role == "print_manager" else legacy_role)
        membership = MakerspaceMembership.objects.create(
            makerspace=makerspace,
            user=make_user(f"fallback-default-{index}", makerspace=makerspace),
            role=legacy_role, assigned_role=primary,
        )
        with pytest.raises(IntegrityError), transaction.atomic():
            MakerspaceMembership.objects.filter(pk=membership.pk).update(assigned_role=None)
            membership.refresh_from_db()
            assert rbac.actions_for_membership(membership) == set()
            assert all(not rbac.can(membership.user, action, makerspace.pk) for action in rbac.ALL_ACTIONS)
            assert rbac.makerspaces_for_action(membership.user, rbac.Action.VIEW_INVENTORY) == set()
            with connection.cursor() as cursor:
                cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
        membership.refresh_from_db()
        assert membership.assigned_role_id == primary.pk


def test_combinable_builtin_roles_control_can_and_action_scopes():
    from tests.fixed_roles.helpers import assign_builtin_roles
    makerspace = make_makerspace("dual-read-narrow")
    user = make_user("narrow-role-user", makerspace=makerspace)
    assign_builtin_roles(user, makerspace, "event_manager", "booking_manager")
    allowed = {rbac.Action.MANAGE_EVENTS, rbac.Action.MANAGE_BOOKINGS}
    for action in rbac.ALL_ACTIONS:
        assert rbac.can(user, action, makerspace.pk) == (action in allowed)
    for action in allowed:
        assert rbac.makerspaces_for_action(user, action) == {makerspace.pk}
        assert set(rbac.scope_by_action(user, action, Makerspace.objects.all(), field="id").values_list("id", flat=True)) == {makerspace.pk}
    assert rbac.makerspaces_for_action(user, rbac.Action.EDIT_INVENTORY) == set()


def test_forbidden_and_malformed_assigned_role_actions_fail_closed():
    makerspace = make_makerspace("dual-read-forbidden")
    role = custom_role(makerspace, "corrupt-role", [rbac.Action.VIEW_INVENTORY])
    user = make_user("corrupt-role-user", makerspace=makerspace)
    membership = MakerspaceMembership.objects.create(
        makerspace=makerspace,
        user=user,
        role=MakerspaceMembership.Role.CUSTOM,
        assigned_role=role,
    )
    MakerspaceRole.objects.filter(pk=role.pk).update(
        granted_actions=[
            rbac.Action.TRANSFER_STOCK,
            rbac.Action.MANAGE_STAFF,
            rbac.Action.EDIT_INVENTORY,
            "not_a_real_action",
            123,
            {"x": 1},
        ]
    )
    membership = MakerspaceMembership.objects.select_related("assigned_role").get(
        pk=membership.pk
    )

    assert rbac.actions_for_membership(membership) == {rbac.Action.EDIT_INVENTORY}
    assert not rbac.can(user, rbac.Action.TRANSFER_STOCK, makerspace.id)
    assert not rbac.can(user, rbac.Action.MANAGE_STAFF, makerspace.id)
    assert rbac.makerspaces_for_action(user, rbac.Action.TRANSFER_STOCK) == set()


def test_cross_tenant_assigned_role_fails_closed_without_legacy_fallback():
    makerspace_a = make_makerspace("dual-read-tenant-a")
    makerspace_b = make_makerspace("dual-read-tenant-b")
    user = make_user("cross-tenant-role-user", makerspace=makerspace_a)
    membership = MakerspaceMembership.objects.create(
        makerspace=makerspace_a,
        user=user,
        role=MakerspaceMembership.Role.SPACE_MANAGER,
        assigned_role=seeded_role(makerspace_a, MakerspaceMembership.Role.SPACE_MANAGER),
    )
    foreign_role = custom_role(makerspace_b, "foreign-role", [rbac.Action.VIEW_INVENTORY])
    with pytest.raises(IntegrityError), transaction.atomic():
        MakerspaceMembership.objects.filter(pk=membership.pk).update(
            assigned_role_id=foreign_role.id
        )
        membership = MakerspaceMembership.objects.select_related("assigned_role").get(
            pk=membership.pk
        )

        assert rbac.actions_for_membership(membership) == set()
        assert all(not rbac.can(user, action, makerspace_a.id) for action in rbac.ALL_ACTIONS)
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")



def test_superadmin_is_always_on_even_where_the_retired_access_flag_is_off():
    makerspace = make_makerspace(
        "dual-read-flag-off"
    )
    superadmin = make_user(
        "always-on-superadmin",
        role=User.Role.SUPERADMIN,
        is_superuser=True,
        is_staff=True,
    )

    for action in rbac.ALL_ACTIONS:
        assert rbac.can(superadmin, action, makerspace.id)
        assert rbac.makerspaces_for_action(superadmin, action) is rbac.ALL
    assert rbac.effective_actions(superadmin, makerspace.id) == set(rbac.ROLE_GRANTABLE_ACTIONS)
    assert rbac.is_space_manager_identity(superadmin, makerspace.id)
    assert rbac.resolve_scope(superadmin) is rbac.ALL

    separate_staff = make_user("flag-off-staff", makerspace=makerspace)
    MakerspaceMembership.objects.create(makerspace=makerspace, user=separate_staff,
        role="event_manager", assigned_role=makerspace.roles.get(slug="event_manager"))
    assert rbac.can(separate_staff, rbac.Action.MANAGE_EVENTS, makerspace.id)
    assert not rbac.can(separate_staff, rbac.Action.EDIT_INVENTORY, makerspace.id)
    assert rbac.makerspaces_for_action(separate_staff, rbac.Action.MANAGE_EVENTS) == {makerspace.pk}


def test_archived_makerspaces_deny_members_and_superadmins_and_leave_all_scopes():
    makerspace = make_makerspace("dual-read-archived")
    user = make_user("archived-member", makerspace=makerspace)
    MakerspaceMembership.objects.create(
        makerspace=makerspace,
        user=user,
        role=MakerspaceMembership.Role.SPACE_MANAGER,
        assigned_role=seeded_role(makerspace, MakerspaceMembership.Role.SPACE_MANAGER),
    )
    superadmin = make_user(
        "archived-superadmin",
        role=User.Role.SUPERADMIN,
        is_superuser=True,
        is_staff=True,
    )
    makerspace.archived_at = timezone.now()
    makerspace.save(update_fields=["archived_at"])

    assert not rbac.can(user, rbac.Action.VIEW_INVENTORY, makerspace.id)
    assert not rbac.can(superadmin, rbac.Action.VIEW_INVENTORY, makerspace.id)
    assert rbac.resolve_scope(user) == set()
    assert rbac.makerspaces_for_action(user, rbac.Action.VIEW_INVENTORY) == set()
    assert rbac.makerspaces_for_action(superadmin, rbac.Action.VIEW_INVENTORY) == set()
    assert not rbac.scope_by_makerspace(user, Makerspace.objects.all()).exists()
    assert not rbac.scope_by_action(
        superadmin, rbac.Action.VIEW_INVENTORY, Makerspace.objects.all()
    ).exists()


def test_visible_global_superadmin_preserves_all_fast_paths():
    make_makerspace("dual-read-visible")
    superadmin = make_user(
        "visible-superadmin",
        role=User.Role.SUPERADMIN,
        is_superuser=True,
        is_staff=True,
    )

    assert rbac.resolve_scope(superadmin) is rbac.ALL
    assert rbac.makerspaces_for_action(superadmin, rbac.Action.VIEW_INVENTORY) is rbac.ALL


def test_string_makerspace_ids_match_integer_ids_and_membership_role_stays_display_only():
    makerspace = make_makerspace("dual-read-string-id")
    user = make_user("string-id-user", makerspace=makerspace)
    MakerspaceMembership.objects.create(
        makerspace=makerspace,
        user=user,
        role=MakerspaceMembership.Role.PRINT_MANAGER,
        assigned_role=seeded_role(makerspace, MakerspaceMembership.Role.MACHINE_MANAGER),
    )

    assert rbac.can(user, rbac.Action.MANAGE_PRINTING, str(makerspace.id)) == rbac.can(
        user, rbac.Action.MANAGE_PRINTING, makerspace.id
    )
    # Compatibility/display only: authority above is resolved from assigned-role actions.
    assert rbac.membership_role(user, makerspace.id) == MakerspaceMembership.Role.PRINT_MANAGER

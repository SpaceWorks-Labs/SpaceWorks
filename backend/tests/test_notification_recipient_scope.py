"""Object scoping on recipient rules (Notifications v2, N4).

Composition is `object_scope AND (rule_scope OR all)` for every kind — it can only ever NARROW. The two
halves fail in opposite directions on purpose and this file pins both: an unscoped *rule*
matches everything (an operator who did not narrow it), while an unscoped machine-managing
*role* reaches nothing (access fails closed). Getting either backwards is either a silent
mute or an alert about hardware the recipient would 403 on.
"""
from django.db import IntegrityError, connection, transaction
from tests.account_split.sweep_helpers import (
    configured_membership as _configured_membership,
    make_role_account as _make_role_account,
)

import pytest
from django.contrib.auth import get_user_model

from apps.accounts.models import User
from apps.accounts.rbac import Action
from apps.integrations.destinations import NotificationScope
from apps.integrations.models_recipients import (
    NotificationRecipient,
    NotificationRecipientKind,
)
from apps.integrations.staff_notifications import (
    staff_emails_for_feature,
    staff_user_ids_for_feature,
)
from apps.machines.models import Machine, MachineType
from apps.makerspaces.models import Makerspace, MakerspaceMembership, MakerspaceRole
from apps.makerspaces.roles import ensure_default_roles

pytestmark = pytest.mark.django_db


def make_space(slug):
    space = Makerspace.objects.create(name=slug, slug=slug)
    ensure_default_roles(space)
    return space


def make_machine(space, name):
    machine_type = MachineType.objects.create(
        makerspace=space, name=f"{name}-type", slug=f"{space.slug}-{name}-type"
    )
    return Machine.objects.create(makerspace=space, machine_type=machine_type, name=name)


def make_role(space, slug, actions):
    from tests.fixed_roles.helpers import roles_for_actions
    return roles_for_actions(space, actions)[0]


def make_member(username, space, role):
    user = _make_role_account(
        space,
        role_slug=(role).slug,
        username=username,
        email=f"{username}@e.com",
        role=User.Role.REQUESTER,
        access_status=User.AccessStatus.ACTIVE,
    )
    _configured_membership(user=user, makerspace=space)
    return user


def select_role(space, role, event="logged", feature="maintenance"):
    return NotificationRecipient.objects.create(
        makerspace=space,
        feature=feature,
        event=event,
        kind=NotificationRecipientKind.ROLE,
        role=role,
    )


def emails(space, machine, event="logged"):
    return staff_emails_for_feature(
        space, "maintenance", event=event, scope=NotificationScope(machine=machine)
    )


def email_and_push_recipients(space, machine):
    scope = NotificationScope(machine=machine)
    return (
        staff_emails_for_feature(space, "maintenance", event="logged", scope=scope),
        staff_user_ids_for_feature(space, "maintenance", event="logged", scope=scope),
    )


# --- subject-aware fallback ----------------------------------------------------------


def test_a_rule_for_another_machine_falls_back_for_email_and_native_push():
    space = make_space("rulescope-subject-fallback")
    laser = make_machine(space, "laser")
    printer = make_machine(space, "printer")
    manager_role = make_role(space, "machine-manager", [Action.MANAGE_MACHINES])
    manager = make_member("rulescope-subject-default", space, manager_role)
    member_role = MakerspaceRole.objects.get(makerspace=space, slug="member")
    selected = make_member("rulescope-subject-selected", space, member_role)
    rule = NotificationRecipient.objects.create(
        makerspace=space,
        feature="maintenance",
        event="logged",
        kind=NotificationRecipientKind.USER,
        user=selected,
    )
    rule.machine_scopes.create(machine=laser)

    assert email_and_push_recipients(space, printer) == ([manager.email], [manager.pk])


def test_a_rule_covering_the_subject_stays_authoritative_for_email_and_push():
    space = make_space("rulescope-subject-authoritative")
    laser = make_machine(space, "laser")
    manager_role = make_role(space, "machine-manager", [Action.MANAGE_MACHINES])
    make_member("rulescope-authoritative-default", space, manager_role)
    member_role = MakerspaceRole.objects.get(makerspace=space, slug="member")
    selected = make_member("rulescope-authoritative-selected", space, member_role)
    # An operator of the laser can see it, so the #75c object floor admits them.
    from apps.machines.models import MachineOperator
    MachineOperator.objects.create(machine=laser, user=selected, access_level=MachineOperator.AccessLevel.OPERATE)
    rule = NotificationRecipient.objects.create(
        makerspace=space,
        feature="maintenance",
        event="logged",
        kind=NotificationRecipientKind.USER,
        user=selected,
    )
    rule.machine_scopes.create(machine=laser)

    assert email_and_push_recipients(space, laser) == ([selected.email], [selected.pk])


def test_no_rows_keeps_the_action_default_for_email_and_native_push():
    space = make_space("rulescope-no-rows-default")
    printer = make_machine(space, "printer")
    manager_role = make_role(space, "machine-manager", [Action.MANAGE_MACHINES])
    manager = make_member("rulescope-no-rows-manager", space, manager_role)

    assert email_and_push_recipients(space, printer) == ([manager.email], [manager.pk])


# --- rule scope: no links means everything -------------------------------------------


def test_an_unnarrowed_rule_matches_every_subject():
    space = make_space("rulescope-open")
    laser = make_machine(space, "laser")
    printer = make_machine(space, "printer")
    role = make_role(space, "machine-team", [Action.MANAGE_MACHINES])
    member = make_member("rulescope-open-member", space, role)
    member.makerspace_memberships.get(makerspace=space).machine_type_scopes.create(machine_type=laser.machine_type)
    member.makerspace_memberships.get(makerspace=space).machine_type_scopes.create(machine_type=printer.machine_type)
    select_role(space, role)

    assert emails(space, laser) == [member.email]
    assert emails(space, printer) == [member.email]


def test_a_narrowed_rule_only_matches_what_it_names():
    space = make_space("rulescope-narrow")
    laser = make_machine(space, "laser")
    printer = make_machine(space, "printer")
    role = make_role(space, "machine-team", [Action.MANAGE_MACHINES])
    member = make_member("rulescope-narrow-member", space, role)
    member.makerspace_memberships.get(makerspace=space).machine_type_scopes.create(machine_type=laser.machine_type)
    member.makerspace_memberships.get(makerspace=space).machine_type_scopes.create(machine_type=printer.machine_type)
    rule = select_role(space, role)
    rule.machine_scopes.create(machine=laser)

    assert emails(space, laser) == [member.email]
    # No explicit row covers the printer, so delivery fails open to the action default.
    assert emails(space, printer) == [member.email]


def test_rule_narrowing_is_a_union_of_machine_type_and_machine():
    space = make_space("rulescope-union")
    laser = make_machine(space, "laser")
    printer_a = make_machine(space, "printer-a")
    printer_b = make_machine(space, "printer-b")
    role = make_role(space, "machine-team", [Action.MANAGE_MAKERSPACE, Action.MANAGE_MACHINES])
    member = make_member("rulescope-union-member", space, role)
    rule = select_role(space, role)
    rule.machine_type_scopes.create(machine_type=printer_a.machine_type)
    rule.machine_scopes.create(machine=laser)

    assert emails(space, laser) == [member.email]
    assert emails(space, printer_a) == [member.email]
    assert emails(space, printer_b) == [member.email]


def test_a_narrowed_rule_without_an_alert_subject_falls_back_to_the_default():
    space = make_space("rulescope-no-subject")
    laser = make_machine(space, "laser")
    # MANAGE_MACHINES is required, not incidental: the action-based default for the
    # `maintenance` feature is `_FEATURE_ACTIONS["maintenance"] = MANAGE_MACHINES`, and
    # MANAGE_MAKERSPACE does NOT imply it (only the reverse implication exists). Without it
    # this asserts a fallback onto an audience the member is not part of, and the empty
    # result would be correct behaviour rather than the bug the test is named for.
    role = make_role(
        space, "machine-team", [Action.MANAGE_MAKERSPACE, Action.MANAGE_MACHINES]
    )
    member = make_member("rulescope-no-subject-member", space, role)
    rule = select_role(space, role)
    rule.machine_scopes.create(machine=laser)

    assert staff_emails_for_feature(space, "maintenance", event="logged") == [member.email]


# --- role scope is the floor, and it can only narrow ---------------------------------


def test_a_rule_naming_a_machine_outside_the_roles_scope_yields_nobody():
    """The composition's whole point: never alert about hardware they would 403 on."""
    space = make_space("rolescope-floor")
    laser = make_machine(space, "laser")
    printer = make_machine(space, "printer")
    role = make_role(space, "laser-team", [Action.MANAGE_MACHINES])
    member = make_member("rolescope-floor-member", space, role)
    member.makerspace_memberships.get(makerspace=space).machine_type_scopes.create(machine_type=laser.machine_type)
    rule = select_role(space, role)
    # The operator narrowed the rule to the printer, which this role cannot reach.
    rule.machine_scopes.create(machine=printer)

    assert emails(space, printer) == []
    assert emails(space, laser) == [member.email]


def test_the_role_floor_applies_even_with_no_rule_narrowing():
    space = make_space("rolescope-floor-open-rule")
    laser = make_machine(space, "laser")
    printer = make_machine(space, "printer")
    role = make_role(space, "laser-team", [Action.MANAGE_MACHINES])
    member = make_member("rolescope-floor-open-member", space, role)
    member.makerspace_memberships.get(makerspace=space).machine_type_scopes.create(machine_type=laser.machine_type)
    select_role(space, role)

    assert emails(space, laser) == [member.email]
    assert emails(space, printer) == []


def test_a_space_manager_role_is_exempt_from_the_floor():
    space = make_space("rolescope-exempt")
    printer = make_machine(space, "printer")
    role = MakerspaceRole.objects.get(makerspace=space, slug="space_manager")
    member = make_member("rolescope-exempt-member", space, role)
    select_role(space, role)

    # A space manager covers every machine, including types created later — making them
    # enumerate types to administer their own lab is the worse failure.
    assert emails(space, printer) == [member.email]


def test_a_legacy_membership_with_no_assigned_role_is_not_stripped():
    space = make_space("rolescope-legacy")
    printer = make_machine(space, "printer")
    role = make_role(space, "machine-team", [Action.MANAGE_MACHINES])
    legacy = _make_role_account(
        space,
        role_slug=(make_role(space, "machine-team", [Action.MANAGE_MACHINES])).slug,
        username="rolescope-legacy-member",
        email="rolescope-legacy-member@e.com",
        role=User.Role.REQUESTER,
        access_status=User.AccessStatus.ACTIVE,
    )
    membership = _configured_membership(user=legacy, makerspace=space)
    # A null assigned_role resolves through the frozen legacy fallback, which is not a
    # role row and has nothing to link — scoping it would silently strip the membership.
    with pytest.raises(IntegrityError), transaction.atomic():
        MakerspaceMembership.objects.filter(pk=membership.pk).update(assigned_role=None)
        select_role(space, role)

        # The rule names the role, and this membership no longer holds it, so it is not
        # selected at all — the floor is not what excluded them.
        assert emails(space, printer) == []
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")


# --- the floor applies to EVERY kind (owner decision #75c, audit NM-71) -----------------


def test_the_member_body_is_filtered_by_whether_each_person_can_see_the_machine():
    """A plain member cannot see the printer in the console, so the floor drops them; an
    operator of that printer can, so they stay."""
    from apps.machines.models import MachineOperator

    space = make_space("rolescope-members")
    printer = make_machine(space, "printer")
    member_role = MakerspaceRole.objects.get(makerspace=space, slug="member")
    plain = make_member("rolescope-members-member", space, member_role)
    operator = make_member("rolescope-members-operator", space, member_role)
    MachineOperator.objects.create(machine=printer, user=operator, access_level=MachineOperator.AccessLevel.OPERATE)
    NotificationRecipient.objects.create(
        makerspace=space,
        feature="maintenance",
        event="logged",
        kind=NotificationRecipientKind.MEMBERS,
    )

    assert emails(space, printer) == [operator.email]
    assert plain.email not in emails(space, printer)


def test_a_named_individual_without_machine_visibility_is_filtered():
    space = make_space("rolescope-named")
    printer = make_machine(space, "printer")
    member_role = MakerspaceRole.objects.get(makerspace=space, slug="member")
    named = make_member("rolescope-named-member", space, member_role)
    NotificationRecipient.objects.create(
        makerspace=space,
        feature="maintenance",
        event="logged",
        kind=NotificationRecipientKind.USER,
        user=named,
    )

    assert emails(space, printer) == []


def test_a_named_individual_is_still_narrowed_by_the_rule():
    from apps.machines.models import MachineOperator

    space = make_space("rolescope-named-narrow")
    laser = make_machine(space, "laser")
    printer = make_machine(space, "printer")
    member_role = MakerspaceRole.objects.get(makerspace=space, slug="member")
    named = make_member("rolescope-named-narrow-member", space, member_role)
    for machine in (laser, printer):
        MachineOperator.objects.create(machine=machine, user=named, access_level=MachineOperator.AccessLevel.OPERATE)
    rule = NotificationRecipient.objects.create(
        makerspace=space,
        feature="maintenance",
        event="logged",
        kind=NotificationRecipientKind.USER,
        user=named,
    )
    rule.machine_scopes.create(machine=laser)

    assert emails(space, laser) == [named.email]
    assert emails(space, printer) == []


# --- features with no subject are unaffected -----------------------------------------


def test_scoping_does_not_disturb_a_feature_that_names_no_machine():
    space = make_space("rolescope-events")
    role = make_role(space, "events-team", [Action.MANAGE_EVENTS])
    member = make_member("rolescope-events-member", space, role)
    select_role(space, role, event="published", feature="events")

    # Events carry no machine, so neither half of the composition applies and the
    # selection resolves exactly as it did before N4.
    assert staff_emails_for_feature(space, "events", event="published") == [member.email]

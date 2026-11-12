"""Per-person type scoping of MANAGE_MACHINES (`machines.role_scope`).

The behaviour under test is a narrowing, so most of these assert what an actor can NO
LONGER reach. The two that matter most are the fail-closed default (a role with the grant
and no links reaches nothing) and the two exemptions that keep it from being a regression
for space managers and legacy memberships.
"""

from apps.machines.models_membership_scope import MembershipMachineTypeScope


import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.accounts import rbac
from apps.accounts.models import User
from apps.accounts.rbac import Action
from apps.machines import access, role_scope
from apps.machines.models import Machine, MachineType
from apps.makerspaces.models import Makerspace, MakerspaceMembership, MakerspaceRole

from tests.account_split_g2_helpers import staff_for_actions, rejected_account_rows

pytestmark = pytest.mark.django_db


def make_space(slug):
    return Makerspace.objects.create(name=slug, slug=slug)


def make_type(slug, makerspace=None, managing_action=""):
    return MachineType.objects.create(
        slug=slug,
        name=slug.replace("-", " ").title(),
        makerspace=makerspace,
        is_builtin=makerspace is None,
        managing_action=managing_action,
    )


def make_machine(space, machine_type, name="machine"):
    return Machine.objects.create(
        makerspace=space, machine_type=machine_type, name=name
    )


def make_scoped_manager(username, space, *, actions=(Action.MANAGE_MACHINES,), slug="machine-team"):
    return staff_for_actions(space, username, actions)


def test_a_role_with_the_grant_and_no_links_reaches_no_machine():
    # The whole point of the mechanism: MANAGE_MACHINES is no longer self-sufficient.
    space = make_space("scope-failclosed")
    printer_type = make_type("failclosed-printer", space)
    machine = make_machine(space, printer_type)
    actor, _ = make_scoped_manager("failclosed-mgr", space)

    assert rbac.can(actor, Action.MANAGE_MACHINES, space.id) is True
    assert access.is_machine_admin(actor, machine) is False
    assert access.can_manage_machine(actor, machine) is False
    assert access.scope_machines_for_actor(actor, Machine.objects.all()).count() == 0
    # A tab that renders an empty list and 403s on every action is worse than no tab.
    assert access.can_see_machines(actor, space.id) is False


def test_a_type_link_covers_that_type_and_only_that_type():
    space = make_space("scope-bytype")
    printers = make_type("bytype-printer", space)
    lasers = make_type("bytype-laser", space)
    printer = make_machine(space, printers, name="printer")
    laser = make_machine(space, lasers, name="laser")
    actor, role = make_scoped_manager("bytype-mgr", space)
    MembershipMachineTypeScope.objects.create(membership=role, machine_type=printers)

    assert access.is_machine_admin(actor, printer) is True
    assert access.is_machine_admin(actor, laser) is False

    visible = access.scope_machines_for_actor(actor, Machine.objects.all())
    assert list(visible.values_list("pk", flat=True)) == [printer.pk]


def test_a_type_link_also_covers_a_machine_registered_later():
    # Why the backfill links types rather than machines: coverage must not freeze at the
    # fleet as it stood when the link was made.
    space = make_space("scope-future")
    printers = make_type("future-printer", space)
    actor, role = make_scoped_manager("future-mgr", space)
    MembershipMachineTypeScope.objects.create(membership=role, machine_type=printers)

    later = make_machine(space, printers, name="bought-later")

    assert access.is_machine_admin(actor, later) is True


def test_creating_a_machine_requires_a_type_link():
    space = make_space("scope-create")
    printers = make_type("create-printer", space)
    lasers = make_type("create-laser", space)
    actor, role = make_scoped_manager("create-mgr", space)
    MembershipMachineTypeScope.objects.create(membership=role, machine_type=printers)

    assert access.can_create_machine(actor, space.id, printers) is True
    assert access.can_create_machine(actor, space.id, lasers) is False


def test_manage_makerspace_is_exempt_including_types_created_later():
    space = make_space("scope-exempt-sm")
    actor, _ = make_scoped_manager(
        "exempt-sm",
        space,
        actions=(Action.MANAGE_MACHINES, Action.MANAGE_MAKERSPACE),
        slug="space-boss",
    )
    invented_afterwards = make_type("exempt-invented", space)
    machine = make_machine(space, invented_afterwards)

    assert role_scope.manage_scope_for(actor, space.id) is role_scope.EXEMPT
    assert access.is_machine_admin(actor, machine) is True
    assert access.can_create_machine(actor, space.id, invented_afterwards) is True


def test_a_null_role_fk_membership_fails_closed_and_is_rejected():
    space = make_space("scope-legacy")
    printer_type = make_type("legacy-printer", space)
    machine = make_machine(space, printer_type)
    user, membership = make_scoped_manager("legacy-machine-mgr", space)
    with rejected_account_rows():
        MakerspaceMembership.staff_tracks.filter(pk=membership.pk).update(assigned_role=None)
        assert role_scope.manage_scope_for(user, space.pk) == role_scope.NOTHING
        assert access.is_machine_admin(user, machine) is False
        assert access.can_create_machine(user, space.pk, printer_type) is False
        assert access.scope_machines_for_actor(user, Machine.objects.all()).count() == 0
        assert space.pk not in role_scope.makerspaces_granting_directly(user, Action.MANAGE_MACHINES)


def test_scoping_never_reaches_across_makerspaces():
    space = make_space("scope-tenant-a")
    other = make_space("scope-tenant-b")
    shared_builtin = make_type("tenant-shared-builtin")
    ours = make_machine(space, shared_builtin, name="ours")
    theirs = make_machine(other, shared_builtin, name="theirs")
    actor, role = make_scoped_manager("tenant-mgr", space)
    # A link to a GLOBAL built-in type must not spill into another tenant's fleet.
    MembershipMachineTypeScope.objects.create(membership=role, machine_type=shared_builtin)

    visible = set(
        access.scope_machines_for_actor(actor, Machine.objects.all()).values_list(
            "pk", flat=True
        )
    )
    assert visible == {ours.pk}
    assert theirs.pk not in visible


def test_a_cross_tenant_link_is_inert_rather_than_a_leak():
    # The write boundary rejects this; resolution must not depend on that having worked.
    space = make_space("scope-mislink-a")
    other = make_space("scope-mislink-b")
    their_type = make_type("mislink-type", other)
    their_machine = make_machine(other, their_type)
    actor, role = make_scoped_manager("mislink-mgr", space)
    MembershipMachineTypeScope.objects.create(membership=role, machine_type=their_type)

    assert access.is_machine_admin(actor, their_machine) is False
    assert (
        access.scope_machines_for_actor(actor, Machine.objects.all()).count() == 0
    )


def test_legacy_print_manager_role_cannot_restore_type_manager_authority():
    space = make_space("scope-tiers")
    printers = make_type("tiers-printer", space, managing_action=Action.MANAGE_PRINTING)
    printer = make_machine(space, printers)
    printer_mgr, membership = make_scoped_manager("tiers-printmgr", space)
    with rejected_account_rows():
        MakerspaceMembership.staff_tracks.filter(pk=membership.pk).update(
            assigned_role=None, role="print_manager",
        )
        assert access.is_machine_admin(printer_mgr, printer) is False
        assert access.can_create_machine(printer_mgr, space.pk, printers) is False
        assert space.pk not in role_scope.makerspaces_granting_directly(printer_mgr, Action.MANAGE_PRINTING)


def test_bulk_capabilities_stay_query_constant_under_scoping():
    space = make_space("scope-queries")
    printers = make_type("queries-printer", space)
    actor, role = make_scoped_manager("queries-mgr", space)
    MembershipMachineTypeScope.objects.create(membership=role, machine_type=printers)
    for index in range(3):
        make_machine(space, printers, name=f"m{index}")

    def measure(count):
        machines = list(
            Machine.objects.select_related("machine_type").all()[:count]
        )
        with CaptureQueriesContext(connection) as captured:
            access.capabilities_for_machines(actor, machines)
        return len(captured)

    assert measure(1) == measure(3)

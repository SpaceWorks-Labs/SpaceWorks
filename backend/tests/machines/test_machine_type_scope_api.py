"""Machine-type access list behavior under role and object scoping."""

from apps.machines.models_membership_scope import MembershipMachineTypeScope


import pytest
from django.db.models import Q
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.rbac import Action
from apps.machines.models import (
    Machine,
    MachineOperator,
    MachineType,
)
from apps.makerspaces.models import Makerspace, MakerspaceMembership, MakerspaceRole

from tests.account_split.p1_helpers import staff
from tests.account_split_g2_helpers import staff_for_actions, rejected_account_rows

pytestmark = pytest.mark.django_db


def _user(username):
    return User.objects.create_user(
        username=username,
        email=f"{username}@example.test",
        role=User.Role.REQUESTER,
        access_status=User.AccessStatus.ACTIVE,
    )


def _role_actor(space, username, actions=(Action.MANAGE_MACHINES,)):
    return staff_for_actions(space, username, actions)


def _list(actor, space):
    client = APIClient()
    client.force_authenticate(user=actor)
    response = client.get(reverse("admin-machine-types", args=[space.pk]))
    assert response.status_code == 200
    return {row["id"]: row for row in response.data}


@pytest.fixture
def type_lab():
    space = Makerspace.objects.create(name="Type scope lab", slug="type-scope-lab")
    laser = MachineType.objects.create(
        makerspace=space, slug="type-scope-laser", name="Laser"
    )
    printer = MachineType.objects.create(
        makerspace=space, slug="type-scope-printer", name="Printer"
    )
    unreachable = MachineType.objects.create(
        makerspace=space, slug="type-scope-kiln", name="Kiln"
    )
    return space, laser, printer, unreachable


def test_type_list_omits_unreachable_types(type_lab):
    space, laser, printer, unreachable = type_lab
    actor, role = _role_actor(space, "type-list-laser")
    MembershipMachineTypeScope.objects.create(membership=role, machine_type=laser)

    rows = _list(actor, space)

    assert laser.pk in rows
    assert printer.pk not in rows
    assert unreachable.pk not in rows


def test_linked_zero_machine_type_is_returned_with_create_authority(type_lab):
    space, laser, _, _ = type_lab
    actor, role = _role_actor(space, "type-list-zero")
    MembershipMachineTypeScope.objects.create(membership=role, machine_type=laser)

    rows = _list(actor, space)

    assert not Machine.objects.filter(machine_type=laser).exists()
    assert rows[laser.pk]["can_create_machine"] is True


def test_type_link_returns_create_authority(type_lab):
    space, _, printer, _ = type_lab
    actor, role = _role_actor(space, "type-list-type-link")
    MembershipMachineTypeScope.objects.create(membership=role, machine_type=printer)

    assert _list(actor, space)[printer.pk]["can_create_machine"] is True


def test_two_type_scoped_roles_each_see_only_their_type(type_lab):
    space, laser, printer, _ = type_lab
    laser_actor, laser_role = _role_actor(space, "type-list-team-laser")
    printer_actor, printer_role = _role_actor(space, "type-list-team-printer")
    MembershipMachineTypeScope.objects.create(membership=laser_role, machine_type=laser)
    MembershipMachineTypeScope.objects.create(membership=printer_role, machine_type=printer)

    assert set(_list(laser_actor, space)) == {laser.pk}
    assert set(_list(printer_actor, space)) == {printer.pk}


def test_space_manager_identity_sees_every_applicable_type(type_lab):
    space, laser, printer, unreachable = type_lab
    manager = staff(space, "type-list-space-manager", "space_manager", access_status="active")[0]
    applicable_ids = set(
        MachineType.objects.filter(
            Q(makerspace__isnull=True) | Q(makerspace=space)
        ).values_list("pk", flat=True)
    )

    rows = _list(manager, space)

    assert set(rows) == applicable_ids
    assert {laser.pk, printer.pk, unreachable.pk} <= set(rows)
    assert all(row["can_create_machine"] is True for row in rows.values())


def test_legacy_print_manager_cannot_reach_zero_machine_type(type_lab):
    space, _, _, _ = type_lab
    managed = MachineType.objects.create(
        makerspace=space, slug="type-scope-direct", name="Directly managed",
        managing_action=Action.MANAGE_PRINTING,
    )
    actor, membership = _role_actor(space, "type-list-direct-manager")
    with rejected_account_rows():
        MakerspaceMembership.objects.filter(pk=membership.pk).update(
            assigned_role=None, role="print_manager",
        )
        client = APIClient()
        client.force_authenticate(actor)
        response = client.get(reverse("admin-machine-types", args=[space.pk]))
        assert response.status_code == 403
        assert not actor.makerspace_memberships.filter(assigned_role__isnull=False).exists()


def test_per_machine_operator_reaches_type_without_create_authority(type_lab):
    space, _, printer, _ = type_lab
    machine = Machine.objects.create(
        makerspace=space, machine_type=printer, name="Operated printer"
    )
    actor, _ = _role_actor(space, "type-list-operator", actions=())
    MachineOperator.objects.create(
        machine=machine,
        user=actor,
        access_level=MachineOperator.AccessLevel.OPERATE,
    )

    rows = _list(actor, space)

    assert rows[printer.pk]["can_create_machine"] is False

"""Person-specific type assignment reaches current and future machines."""
import pytest
from django.urls import reverse

from apps.machines import access
from apps.machines.models import Machine, MachineType, MachineOperator
from tests.fixed_roles.helpers import assign_builtin_roles
from tests.return_helpers import authenticated_client, make_space, make_user

pytestmark = pytest.mark.django_db


def test_two_people_with_the_same_role_have_independent_type_reach():
    space = make_space("person-type-reach")
    boss = make_user("person-type-boss", access_status="active", account_kind="staff", staff_makerspace=space)
    assign_builtin_roles(boss, space, "space_manager")
    laser, printer = [MachineType.objects.create(makerspace=space, name=name, slug=name.lower())
                      for name in ("Laser", "Printer")]
    machines = [Machine.objects.create(makerspace=space, machine_type=kind, name=kind.name)
                for kind in (laser, printer)]
    people = [make_user(f"person-type-{index}", access_status="active", account_kind="staff", staff_makerspace=space) for index in range(2)]
    memberships = [assign_builtin_roles(person, space, "machine_manager") for person in people]
    client = authenticated_client(boss)
    for person, membership, kind, machine in zip(people, memberships, (laser, printer), machines):
        assert not access.can_see_machines(person, space.pk)
        assert not access.scope_machines_for_actor(person, Machine.objects.all()).exists()
        response = client.put(reverse("admin-membership-machine-scope", args=[space.pk, membership.pk]),
                              {"machine_type_ids": [kind.pk]}, format="json")
        assert response.status_code == 200, response.data
        assert access.can_manage_machine(person, machine)
    assert memberships[0].assigned_role_id == memberships[1].assigned_role_id
    assert not access.can_manage_machine(people[0], machines[1])
    assert not access.can_manage_machine(people[1], machines[0])
    later = Machine.objects.create(makerspace=space, machine_type=laser, name="Later laser")
    assert access.can_manage_machine(people[0], later)
    assert not access.can_manage_machine(people[1], later)
    assert access.can_manage_machine(boss, later)
    assert access.can_manage_machine(boss, machines[1])
    assert set(access.scope_machines_for_actor(people[0], Machine.objects.all()).values_list("pk", flat=True)) == {machines[0].pk, later.pk}


def test_assigned_type_with_no_machines_is_visible_and_allows_creation():
    space = make_space("empty-type-reach")
    kind = MachineType.objects.create(makerspace=space, name="Empty kiln", slug="empty-kiln")
    actor = make_user("empty-type-actor", access_status="active", account_kind="staff", staff_makerspace=space)
    assign_builtin_roles(actor, space, "machine_manager", machine_types=[kind])
    assert not Machine.objects.filter(machine_type=kind).exists()
    assert access.can_see_machines(actor, space.pk)
    assert access.can_create_machine(actor, space.pk, kind)
    response = authenticated_client(actor).get(reverse("admin-machine-types", args=[space.pk]))
    assert response.status_code == 200, response.data
    assert {row["id"] for row in response.data} == {kind.pk}


def test_machine_operator_tier_three_still_reaches_only_its_machine():
    space = make_space("operator-type-reach")
    kind = MachineType.objects.create(makerspace=space, name="Lasers", slug="operator-laser")
    first, second = [Machine.objects.create(makerspace=space, machine_type=kind, name=name)
                     for name in ("First", "Second")]
    actor = make_user("operator-type-actor", access_status="active")
    assign_builtin_roles(actor, space, "member")
    MachineOperator.objects.create(machine=first, user=actor, access_level=MachineOperator.AccessLevel.MANAGE)
    assert access.can_manage_machine(actor, first)
    assert not access.can_manage_machine(actor, second)
    assert access.can_see_machines(actor, space.pk)
    assert not access.can_create_machine(actor, space.pk, kind)

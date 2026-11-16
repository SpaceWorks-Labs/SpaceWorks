"""O-B1: the staff and public unit routes -- switches, 404 across tenants, shapes, typed errors."""
import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.makerspaces.models import MembershipPlan
from tests.makerspaces.l4_helpers import features_off, plan, space_with_manager
from tests.parity_0120.o_b1.helpers import community_member, lead, tree, units_space
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db(transaction=True)


def _url(name, space, *args):
    return reverse(name, args=[space.pk, *args])


def test_every_staff_route_is_404_while_units_are_off():
    space, boss = space_with_manager("ob1-api-off")
    client = authenticated_client(boss)
    assert client.get(_url("admin-member-units", space)).status_code == 404
    assert client.put(_url("admin-member-unit-levels", space), {"levels": ["A"]}, format="json").status_code == 404


def test_create_list_edit_move_archive_round_trip_with_shapes():
    space, boss = units_space("ob1-api-tree")
    client = authenticated_client(boss)
    client.put(_url("admin-member-unit-levels", space), {"levels": ["Region", "District"]}, format="json")
    south = client.post(_url("admin-member-units", space), {"name": "South", "code": "SOUTH"}, format="json")
    assert south.status_code == 201 and south.json()["path"] == "/SOUTH/"
    kochi = client.post(_url("admin-member-units", space), {"name": "Kochi", "parent_id": south.json()["id"]},
                        format="json").json()
    listed = client.get(_url("admin-member-units", space)).json()
    assert listed["levels"] == ["Region", "District"] and listed["used"] == 2 and listed["limit"] is None
    assert [unit["code"] for unit in listed["units"]] == ["SOUTH", "KOCHI"] and listed["templates"]
    patched = client.patch(_url("admin-member-unit", space, kochi["id"]),
                           {"payment_instructions": "UPI kochi@bank"}, format="json").json()
    assert patched["effective_payment_instructions"] == "UPI kochi@bank"
    moved = client.post(_url("admin-member-unit-move", space, kochi["id"]), {"parent_id": None}, format="json")
    assert moved.status_code == 200 and moved.json()["path"] == "/KOCHI/"
    assert client.post(_url("admin-member-unit-archive", space, kochi["id"])).json()["archived"] is True
    assert client.post(_url("admin-member-unit-restore", space, kochi["id"])).json()["archived"] is False


def test_another_spaces_unit_and_space_are_404_never_403():
    space, boss = units_space("ob1-api-tenant-a")
    other, other_boss = units_space("ob1-api-tenant-b")
    _south, _kochi, north = tree(other_boss, other)
    client = authenticated_client(boss)
    assert client.get(_url("admin-member-units", other)).status_code == 404
    assert client.patch(_url("admin-member-unit", space, north.pk), {"name": "x"}, format="json").status_code == 404


def test_assign_member_unit_and_staff_scope_through_the_api():
    space, boss = units_space("ob1-api-assign")
    south, _kochi, _north = tree(boss, space)
    person = community_member(space, "ob1-api-person")
    actor, staff = lead(space, "ob1-api-lead")
    client = authenticated_client(boss)
    placed = client.put(_url("admin-membership-unit", space, person.pk), {"unit_id": south.pk}, format="json")
    assert placed.status_code == 200 and placed.json()["unit"]["code"] == "SOUTH"
    scoped = client.put(_url("admin-staff-unit-scope", space, staff.pk), {"unit_id": south.pk}, format="json")
    assert scoped.status_code == 200 and scoped.json()["unit"]["id"] == south.pk
    # a scoped lead cannot change another staff member's scope (a space-wide act)
    denied = authenticated_client(actor).put(_url("admin-staff-unit-scope", space, staff.pk), {"unit_id": None},
                                             format="json")
    assert denied.status_code in (403, 404)
    features_off(space, "unit_scoped_staff")
    assert client.put(_url("admin-staff-unit-scope", space, staff.pk), {"unit_id": None},
                      format="json").status_code == 404


def test_plan_units_and_the_public_picker():
    space, boss = units_space("ob1-api-plan")
    south, _kochi, _north = tree(boss, space)
    limited = plan(space, "Southern")
    client = authenticated_client(boss)
    put = client.put(_url("admin-plan-units", space, limited.pk), {"unit_ids": [south.pk]}, format="json")
    assert put.status_code == 200 and put.json() == {"unit_ids": [south.pk]}
    public = APIClient().get(reverse("public-member-units", args=[space.slug]) + "?code=kochi")
    body = public.json()
    assert public.status_code == 200 and body["selected"]["code"] == "KOCHI" and body["plan_ids"] == [limited.pk]
    assert {"code", "name", "level", "level_name", "parent_code"} == set(body["units"][0])
    assert MembershipPlan.objects.filter(pk=limited.pk).exists()
    features_off(space, "unit_scoped_staff", "units")
    assert APIClient().get(reverse("public-member-units", args=[space.slug])).status_code == 404

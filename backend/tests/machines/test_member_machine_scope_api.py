"""Membership type-scope editor: replace semantics, choices, and audit."""
import pytest
from django.urls import reverse

from apps.audit.models import AuditLog
from apps.machines.models import MachineType
from apps.makerspaces.models import MakerspaceMembership
from tests.fixed_roles.helpers import assign_builtin_roles
from tests.return_helpers import authenticated_client, make_space, make_user

from tests.account_split.p1_helpers import staff
from tests.account_split_g2_helpers import rejected_account_rows

pytestmark = pytest.mark.django_db


@pytest.fixture
def lab():
    space = make_space("member-scope-editor")
    boss, _ = staff(space, "member-scope-boss", "space_manager", access_status="active")
    actor, membership = staff(space, "member-scope-actor", "machine_manager", access_status="active")
    types = [MachineType.objects.create(makerspace=space, slug=slug, name=slug)
             for slug in ("editor-laser", "editor-printer")]
    url = reverse("admin-membership-machine-scope", args=[space.pk, membership.pk])
    return space, boss, actor, membership, types, url


def test_editor_lists_current_selection_and_local_and_global_choices(lab):
    space, boss, actor, membership, types, url = lab
    assign_builtin_roles(actor, space, "machine_manager", machine_types=[types[0]])
    response = authenticated_client(boss).get(url)
    assert response.status_code == 200, response.data
    assert response.data["membership_id"] == membership.pk
    assert response.data["scoping_applies"] is True
    assert response.data["machine_type_ids"] == [types[0].pk]
    offered = {row["id"] for row in response.data["available_machine_types"]}
    assert {row.pk for row in types} <= offered
    global_ids = set(MachineType.objects.filter(makerspace=None, is_builtin=True).values_list("pk", flat=True))
    assert global_ids <= offered


def test_put_replaces_and_clears_with_audit(lab):
    space, boss, actor, membership, types, url = lab
    assign_builtin_roles(actor, space, "machine_manager", machine_types=[types[0]])
    client = authenticated_client(boss)
    response = client.put(url, {"machine_type_ids": [types[1].pk]}, format="json")
    assert response.status_code == 200, response.data
    assert response.data["machine_type_ids"] == [types[1].pk]
    audit = AuditLog.objects.get(action="staff.machine_scope_changed", makerspace=space)
    assert audit.meta == {"membership_id": membership.pk, "user_id": actor.pk,
                          "before": [types[0].pk], "after": [types[1].pk],
                          "machine_ids_before": [], "machine_ids_after": []}
    assert client.put(url, {"machine_type_ids": []}, format="json").data["machine_type_ids"] == []
    assert not membership.machine_type_scopes.exists()


@pytest.mark.parametrize("invalid", ["unknown", "foreign", "duplicate"])
def test_invalid_ids_return_400_without_losing_selection(lab, invalid):
    space, boss, actor, membership, types, url = lab
    assign_builtin_roles(actor, space, "machine_manager", machine_types=[types[0]])
    ids = [2**62]
    if invalid == "duplicate":
        ids = [types[1].pk, types[1].pk]
    elif invalid == "foreign":
        other = make_space("member-scope-foreign")
        ids = [MachineType.objects.create(makerspace=other, slug="foreign", name="Foreign").pk]
    response = authenticated_client(boss).put(url, {"machine_type_ids": ids}, format="json")
    assert response.status_code == 400, response.data
    assert list(membership.machine_type_scopes.values_list("machine_type_id", flat=True)) == [types[0].pk]
    assert not AuditLog.objects.filter(action="staff.machine_scope_changed").exists()


@pytest.mark.parametrize("role", [None, "space_manager", "event_manager", "member"])
def test_inapplicable_memberships_report_false_and_put_conflicts(lab, role):
    space, boss, actor, membership, _, url = lab
    if role is None:
        with rejected_account_rows():
            MakerspaceMembership.staff_tracks.filter(pk=membership.pk).update(assigned_role=None, role="machine_manager")
            client = authenticated_client(boss)
            response = client.get(url)
            assert response.status_code == 200
            assert response.data["scoping_applies"] is False
            assert client.put(url, {"machine_type_ids": []}, format="json").status_code == 409
        return
    if role == "member":
        member = make_user("member-scope-community", access_status="active")
        membership = assign_builtin_roles(member, space, "member")
        url = reverse("admin-membership-machine-scope", args=[space.pk, membership.pk])
        # Machine scopes hang off staff-track rows only (decision 63, one account per
        # person): a community Member row is not addressable, so it is 404, not 409.
        client = authenticated_client(boss)
        assert client.get(url).status_code == 404
        assert client.put(url, {"machine_type_ids": []}, format="json").status_code == 404
        return
    else:
        assign_builtin_roles(actor, space, role)
    client = authenticated_client(boss)
    response = client.get(url)
    assert response.status_code == 200
    assert response.data["scoping_applies"] is False
    assert client.put(url, {"machine_type_ids": []}, format="json").status_code == 409


def test_machine_manager_cannot_read_or_write_scope(lab):
    _, _, actor, _, _, url = lab
    client = authenticated_client(actor)
    assert client.get(url).status_code == 403
    assert client.put(url, {"machine_type_ids": []}, format="json").status_code == 403

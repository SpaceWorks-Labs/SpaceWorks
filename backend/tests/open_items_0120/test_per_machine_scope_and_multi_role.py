"""0.12.0: per-machine scope (types UNION machines) and multi-role staff. Written for the consolidation run."""
import pytest
from rest_framework.exceptions import ValidationError

from apps.accounts import rbac, staff_account_services as service
from apps.accounts.models import StaffInvitation, User
from apps.audit import area_scope, areas
from apps.audit.models import AuditLog
from apps.audit.services import record
from apps.machines import access, role_scope
from apps.machines.member_scope_services import current_machine_scope, current_scope
from apps.machines.models import Machine
from apps.machines.models_membership_scope import MembershipMachineScope
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from tests.fixed_roles.helpers import _fixture_platform, staff_account
from tests.maintenance.l16_helpers import world

pytestmark = pytest.mark.django_db


def _row(user, space):
    return MakerspaceMembership.staff_tracks.get(user=user, makerspace=space)


def _link_machines(user, space, *machines):
    row = _row(user, space)
    for machine in machines:
        MembershipMachineScope.objects.create(membership=row, machine=machine)
    return row


def _reach(user, space):
    ids = access.scope_machines_for_actor(user, Machine.objects.filter(makerspace=space)).values_list("pk", flat=True)
    return set(ids)


def test_type_only_scope_reaches_every_machine_of_the_type():
    w = world("pm-type")
    user = staff_account(w.space, "pm-type-u", "machine_manager", machine_types=(w.kind,))
    assert _reach(user, w.space) == {w.machine.pk}


def test_machine_only_scope_reaches_just_that_machine():
    w = world("pm-machine")
    extra = Machine.objects.create(makerspace=w.space, machine_type=w.kind, name="Laser B")
    user = staff_account(w.space, "pm-machine-u", "machine_manager")
    _link_machines(user, w.space, w.machine)
    assert _reach(user, w.space) == {w.machine.pk}
    assert extra.pk not in _reach(user, w.space)
    scope = role_scope.manage_scope_for(user, w.space.pk)
    assert role_scope.scope_covers_machine(scope, w.machine) and not role_scope.scope_covers_machine(scope, extra)
    # A machine link cannot create new machines of its type: only a type link can.
    assert not role_scope.scope_covers_type(scope, w.kind)


def test_type_and_machine_links_union():
    w = world("pm-union")
    user = staff_account(w.space, "pm-union-u", "machine_manager", machine_types=(w.kind,))
    _link_machines(user, w.space, w.other)
    assert _reach(user, w.space) == {w.machine.pk, w.other.pk}


def test_nothing_listed_reaches_nothing():
    w = world("pm-none")
    user = staff_account(w.space, "pm-none-u", "machine_manager")
    assert _reach(user, w.space) == set()
    assert role_scope.manage_scope_for(user, w.space.pk) == role_scope.NOTHING
    assert not access.can_see_machines(user, w.space.pk)


def test_cross_space_machine_is_refused_and_inert():
    w, other_world = world("pm-cross"), world("pm-cross-b")
    superadmin = _fixture_platform()
    target = staff_account(w.space, "pm-cross-u", "machine_manager")
    with pytest.raises(ValidationError) as caught:
        service.change(superadmin, w.space.pk, _row(target, w.space).pk, machine_ids=[other_world.machine.pk])
    assert "machine_ids" in caught.value.detail
    # A corrupt link written around the service still confers no authority.
    MembershipMachineScope.objects.create(membership=_row(target, w.space), machine=other_world.machine)
    assert other_world.machine.pk not in _reach(target, w.space)
    from tests.l3_local.helpers import member as community_member  # grant needs a community member (decision 63)
    newcomer = community_member(w.space, "pm-cross-new")[0]
    with pytest.raises(ValidationError):
        service.grant(superadmin, w.space.pk, user_id=newcomer.pk, roles=["machine_manager"],
                      machine_ids=[other_world.machine.pk])


def test_machine_ids_require_a_scoped_role():
    w = world("pm-role")
    superadmin = _fixture_platform()
    user = staff_account(w.space, "pm-role-u", "event_manager")
    with pytest.raises(ValidationError) as caught:
        service.change(superadmin, w.space.pk, _row(user, w.space).pk, machine_ids=[w.machine.pk])
    assert "machine_ids" in caught.value.detail


def test_technician_scoped_by_machine_and_type():
    from apps.maintenance.repairs.authority import technician_covers
    w = world("pm-tech")
    user = staff_account(w.space, "pm-tech-u", "technician")
    assert not technician_covers(user, w.space.pk, rbac.Action.RUN_MAINTENANCE, "machine", w.machine)  # nothing = nothing
    superadmin = _fixture_platform()
    service.change(superadmin, w.space.pk, _row(user, w.space).pk, machine_ids=[w.machine.pk])
    assert technician_covers(user, w.space.pk, rbac.Action.RUN_MAINTENANCE, "machine", w.machine)
    assert not technician_covers(user, w.space.pk, rbac.Action.RUN_MAINTENANCE, "machine", w.other)
    service.change(superadmin, w.space.pk, _row(user, w.space).pk, machine_type_ids=[w.other_kind.pk])
    assert technician_covers(user, w.space.pk, rbac.Action.RUN_MAINTENANCE, "machine", w.other)
    assert current_scope(_row(user, w.space)) == [w.other_kind.pk]
    assert current_machine_scope(_row(user, w.space)) == [w.machine.pk]  # an omitted list is kept


def test_event_plus_booking_manager_sees_both_areas_and_only_those():
    w = world("pm-multi")
    user = staff_account(w.space, "pm-multi-u", "event_manager", "booking_manager")
    actions = rbac.effective_actions(user, w.space.pk)
    assert rbac.Action.MANAGE_EVENTS in actions and rbac.Action.MANAGE_BOOKINGS in actions
    assert areas.areas_for_actions(actions) == {areas.EVENTS, areas.BOOKINGS}
    record(w.manager, "event.created", makerspace=w.space)
    record(w.manager, "booking.approved", makerspace=w.space)
    record(w.manager, "loan.issued", makerspace=w.space)
    seen = set(area_scope.scope_audit_rows(user, AuditLog.objects.filter(makerspace=w.space))
               .values_list("action", flat=True))
    assert {"event.created", "booking.approved"} <= seen and "loan.issued" not in seen


def test_one_machine_manager_plus_inventory_manager_sees_that_machine_and_inventory():
    w = world("pm-mm-im")
    user = staff_account(w.space, "pm-mm-im-u", "machine_manager", "inventory_manager")
    _link_machines(user, w.space, w.machine)
    assert _reach(user, w.space) == {w.machine.pk}
    assert rbac.can(user, rbac.Action.EDIT_INVENTORY, w.space.pk)
    assert rbac.can(user, rbac.Action.MANAGE_MACHINES, w.space.pk)
    assert areas.areas_for_actions(rbac.effective_actions(user, w.space.pk)) >= {areas.MACHINES, areas.LENDING}


def test_scope_change_writes_an_audit_row_with_both_lists():
    w = world("pm-audit")
    superadmin = _fixture_platform()
    user = staff_account(w.space, "pm-audit-u", "machine_manager")
    service.change(superadmin, w.space.pk, _row(user, w.space).pk,
                   machine_type_ids=[w.kind.pk], machine_ids=[w.other.pk])
    row = AuditLog.objects.filter(action="staff.machine_scope_changed", makerspace=w.space).latest("pk")
    assert row.meta["after"] == [w.kind.pk] and row.meta["machine_ids_after"] == [w.other.pk]
    assert row.meta["machine_ids_before"] == []
    changed = AuditLog.objects.filter(action="staff_role.changed", makerspace=w.space).latest("pk")
    assert changed.meta["machine_ids_after"] == [w.other.pk]


def test_dropping_the_scoped_role_clears_both_link_tables():
    w = world("pm-drop")
    superadmin = _fixture_platform()
    user = staff_account(w.space, "pm-drop-u", "machine_manager", machine_types=(w.kind,))
    _link_machines(user, w.space, w.other)
    service.change(superadmin, w.space.pk, _row(user, w.space).pk, roles=["event_manager"])
    row = _row(user, w.space)
    assert current_scope(row) == [] and current_machine_scope(row) == []


def test_invitation_carries_machine_ids_through_acceptance():
    from apps.accounts import services_staff_invitations as invitations
    from apps.accounts.staff_invitation_acceptance import _grant
    w = world("pm-invite")
    Makerspace.objects.filter(pk=w.space.pk).update(
        enabled_modules=sorted({*(w.space.enabled_modules or []), "email"}),
        enabled_features=sorted({*(w.space.enabled_features or []), "staff.invitations"}))
    superadmin = _fixture_platform()
    row, _raw = invitations.issue(superadmin, w.space.pk, email="pm-invitee@example.test",
                                  roles=["machine_manager", "technician"], machine_type_ids=[w.kind.pk],
                                  machine_ids=[w.other.pk])
    row = StaffInvitation.objects.get(pk=row.pk)
    assert row.machine_scope_snapshot == [w.kind.pk] and row.machine_ids_snapshot == [w.other.pk]
    with pytest.raises(ValidationError):
        invitations.issue(superadmin, w.space.pk, email="pm-bad@example.test", roles=["event_manager"],
                          machine_ids=[w.other.pk])
    invitee = User.objects.create_user(username="pm-invitee", email="pm-invitee@example.test", password=None)
    from tests.accounts.account_factories import make_membership
    make_membership(invitee, w.space)
    membership = _grant(invitee, row)
    assert current_scope(membership) == [w.kind.pk] and current_machine_scope(membership) == [w.other.pk]
    assert _reach(invitee, w.space) == {w.machine.pk, w.other.pk}


def test_staff_roles_api_returns_ids_and_names():
    from tests.admin_api.test_staff_roles_api import client_for, url
    w = world("pm-api")
    superadmin = _fixture_platform()
    user = staff_account(w.space, "pm-api-u", "machine_manager", "inventory_manager")
    row = _row(user, w.space)
    api = client_for(superadmin)
    patched = api.patch(url(w.space, row), {"machine_type_ids": [w.kind.pk], "machine_ids": [w.other.pk]},
                        format="json")
    assert patched.status_code == 200, patched.data
    assert patched.data["machine_ids"] == [w.other.pk]
    assert patched.data["machines"] == [{"id": w.other.pk, "name": "CNC A", "machine_type_id": w.other_kind.pk}]
    assert patched.data["machine_types"] == [{"id": w.kind.pk, "name": "Laser"}]
    listed = api.get(url(w.space)).data["policy"]
    assert {entry["id"] for entry in listed["machines"]} >= {w.machine.pk, w.other.pk}
    assert set(listed["scoped_role_slugs"]) == {"machine_manager", "technician"}

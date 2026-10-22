"""D9's object floor for recipients selected as PEOPLE (owner decision #75c).

An alert that names a machine or machine type -- a maintenance fault, a print job, a
certification, a restored booking of a machine-bound room -- carries that object's detail.
Owner decision #75c: the floor applies to EVERY recipient kind, not only `kind=role`
rows (audit NM-71). A person picked by name, or as part of "all members", receives such an
alert only if they could see that object in the console:

* their role's machine reach covers it (`role_scope`: EXEMPT, or the type is linked),
* they manage its type directly (the type's `managing_action`, as `machines.access`), or
* they are an operator of that machine (or, for a type-only alert, of one of its machines), or
* for a ROOM-scoped booking alert (its scope is the room's machine type), they manage bookings
  (`MANAGE_BOOKINGS`) or hold a live staff grant on a room of that type.

A plain member holds none of these, so a machine-scoped alert no longer reaches them through
a members-wide or named selection -- that is the decision, not a side effect. Alerts naming
no machine or type (inventory categories, events, payments) are untouched. Batched: a fixed
number of queries however many memberships are passed.
"""

from django.apps import apps as django_apps

from apps.accounts import rbac
from apps.accounts.rbac_roles import stored_actions_for_membership


def _admits_everyone(membership):
    return True


def _room_viewer_ids(memberships, makerspace_id, type_id):
    """Booking-room visibility: MANAGE_BOOKINGS, or a live grant on a room of that type."""
    ids = {m.user_id for m in memberships if rbac.Action.MANAGE_BOOKINGS in rbac.actions_for_membership(m)}
    try:
        grant_model = django_apps.get_model("bookings", "BookingSpaceStaffGrant")
    except LookupError:  # bookings tombstoned: no rooms, so no room grants
        return ids
    return ids | set(grant_model.objects.filter(
        user_id__in={m.user_id for m in memberships}, makerspace_id=makerspace_id,
        revoked_at__isnull=True, space__machine_type_id=type_id,
    ).values_list("user_id", flat=True))


def person_object_filter(memberships, scope, feature=None):
    """A predicate: may each membership's person see the machine/type (or room) this alert names?"""
    if scope is None or (scope.machine_id is None and scope.machine_type_id is None):
        return _admits_everyone
    memberships = list(memberships)
    if not memberships:
        return _admits_everyone

    from apps.machines import role_scope
    from apps.machines.models import Machine, MachineOperator, MachineType

    makerspace_id = memberships[0].makerspace_id
    type_id = scope.machine_type_id
    if type_id is None:
        type_id = Machine.objects.filter(
            pk=scope.machine_id, makerspace_id=makerspace_id,
        ).values_list("machine_type_id", flat=True).first()
    managing_action = ""
    if type_id is not None:
        managing_action = (
            MachineType.objects.filter(pk=type_id).values_list("managing_action", flat=True).first() or ""
        ).strip()
    operators = MachineOperator.objects.filter(
        user_id__in={membership.user_id for membership in memberships},
        machine__makerspace_id=makerspace_id,
    )
    if scope.machine_id is not None:
        operators = operators.filter(machine_id=scope.machine_id)
    else:
        operators = operators.filter(machine__machine_type_id=type_id)
    operator_ids = set(operators.values_list("user_id", flat=True))
    reach = role_scope.manage_scopes_for_memberships(memberships)
    room_viewers = (
        _room_viewer_ids(memberships, makerspace_id, type_id)
        if feature == "bookings" and type_id is not None else set()
    )

    def sees(membership):
        resolved = reach.get(membership.pk, role_scope.NOTHING)
        if resolved is role_scope.EXEMPT:
            return True
        if type_id is not None and type_id in resolved[0]:
            return True
        if managing_action and managing_action in stored_actions_for_membership(membership):
            return True
        return membership.user_id in operator_ids or membership.user_id in room_viewers

    return sees

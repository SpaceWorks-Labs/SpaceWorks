"""Who may read and triage an incident (decisions 223 (k) and 219 (e)).

The Space Manager (and the superadmin) read every incident in the space. An area manager
reads only the incidents of an area their effective actions open -- the same area
vocabulary the audit log narrows by (`audit.areas`): a Machine Manager the machines area
(narrowed again to their machine types), the Inventory Manager lending, the Events manager
events, the Booking Manager rooms and bookings. The `other` area is the Space Manager's
alone, so an unplaced incident fails closed. The reporter always reads their own.
"""

from django.db.models import Q
from rest_framework.exceptions import NotFound

from apps.accounts import rbac
from apps.audit import areas
from apps.makerspaces.platform import feature_enabled

from .models import Incident
from django.utils.translation import gettext

FEATURE = "safety.incidents"
READER_AREAS = (areas.MACHINES, areas.LENDING, areas.EVENTS, areas.BOOKINGS)


def incidents_on(makerspace):
    return feature_enabled(makerspace, FEATURE)


def require_incidents(makerspace):
    if not incidents_on(makerspace):
        raise NotFound({"detail": gettext("The incident register is switched off for this makerspace."),
                        "code": "feature_disabled", "feature": FEATURE})
    return makerspace


def is_space_manager(actor, makerspace_id):
    return rbac.can(actor, rbac.Action.MANAGE_MAKERSPACE, makerspace_id)


def _held_areas(actor, makerspace_id):
    return {area for area in areas.areas_for_actions(rbac.effective_actions(actor, makerspace_id))
            if area in READER_AREAS}


def visible_incidents(actor, space):
    """Incidents of `space` the actor may read as staff (an empty queryset for none)."""
    base = Incident.objects.filter(makerspace=space)
    if is_space_manager(actor, space.pk):
        return base
    held = _held_areas(actor, space.pk)
    q = Q(pk__in=[])
    for area in held - {areas.MACHINES}:
        q |= Q(area=area)
    if areas.MACHINES in held:
        from apps.machines import role_scope
        from apps.machines.access import scope_machines_for_actor
        from apps.machines.models import Machine
        if role_scope.manage_scope_for(actor, space.pk) is role_scope.EXEMPT:
            q |= Q(area=areas.MACHINES)
        else:
            ids = scope_machines_for_actor(actor, Machine.objects.filter(makerspace=space)).values_list("pk", flat=True)
            q |= Q(area=areas.MACHINES, machine_id__in=list(ids))
    return base.filter(q)


def _technician_machine_ids(actor, space):
    """Decision 242(f): the machines of the types a Technician's in-house coverage names (read only)."""
    if not (rbac.can(actor, rbac.Action.WORK_REPAIRS, space.pk) or rbac.can(actor, rbac.Action.RUN_MAINTENANCE, space.pk)):
        return []
    from apps.machines.models import Machine
    from apps.maintenance.repairs.authority import contact_for
    from apps.maintenance.repairs.authority import membership_reach
    contact = contact_for(actor, space.pk)
    type_ids = [row.machine_type_id for row in contact.coverage.all() if row.kind == "machine_type"] if contact else []
    link_types, link_machines = membership_reach(actor, space.pk)
    return list(Machine.objects.filter(makerspace=space).filter(
        Q(machine_type_id__in=[*type_ids, *link_types]) | Q(pk__in=link_machines)).values_list("pk", flat=True))


def readable_incidents(actor, space):
    """What the actor may READ: the triage reach plus, for a Technician, incidents on covered machine
    types. Handover sees none. Triage stays with `visible_incidents` / `can_triage`."""
    base = visible_incidents(actor, space)
    ids = _technician_machine_ids(actor, space)
    if not ids:
        return base
    return Incident.objects.filter(makerspace=space).filter(
        Q(pk__in=base.values("pk")) | Q(area=areas.MACHINES, machine_id__in=ids))


def can_read(actor, incident):
    return readable_incidents(actor, incident.makerspace).filter(pk=incident.pk).exists()


def can_record(actor, space):
    return is_space_manager(actor, space.pk) or bool(_held_areas(actor, space.pk))


def is_staff_reader(actor, space):
    return (is_space_manager(actor, space.pk) or bool(_held_areas(actor, space.pk))
            or bool(_technician_machine_ids(actor, space)))


def can_triage(actor, incident):
    return visible_incidents(actor, incident.makerspace).filter(pk=incident.pk).exists()


def area_for(*, machine=None, loan=None, event=None, room=None, booking=None, guest_pass=None, repair_issue=None,
             explicit=None):
    """The area an incident belongs to, from what it links to (first match wins).

    A guest pass or a repair issue names no area of its own: it falls to `explicit`, else Other (Space Manager only).
    """
    if machine is not None:
        return Incident.Area.MACHINES
    if loan is not None:
        return Incident.Area.LENDING
    if event is not None:
        return Incident.Area.EVENTS
    if room is not None or booking is not None:
        return Incident.Area.BOOKINGS
    return explicit if explicit in Incident.Area.values else Incident.Area.OTHER

"""What the repairs report family (RP-5) may show one viewer in one space.

The reports reuse the repairs authority rather than inventing a second one:

* issue rows are `authority.visible_issues` -- each area's manager in their own scope
  (a Machine Manager only on the machine types their role covers), plus a Technician's
  own assigned jobs;
* work-order rows are the same areas for managers, plus a Technician's own orders (the
  order's assignee, or an issue assigned to them) and the scheduled maintenance orders
  their in-house coverage names -- the read-side twin of `technician_may_work_order`.

An area counts only while one of its repairs or maintenance switches is on (#128 C-9).
"""

from django.db.models import Q

from apps.accounts import rbac

from . import areas, authority

Action = rbac.Action
INVENTORY_SUBJECTS = ("inventory_product", "inventory_asset")
AREA_SUBJECTS = {areas.MACHINES: ("machine",), areas.INVENTORY: INVENTORY_SUBJECTS,
                 areas.ROOMS: ("bookable_space",)}


def _area_q(area_list):
    return Q(subject_type__in=[subject for area in area_list for subject in AREA_SUBJECTS[area]])


def work_order_areas(space):
    return [area for area in areas.AREAS
            if areas.on(space, areas.REPAIRS[area]) or areas.on(space, areas.MAINTENANCE[area])]


def _coverage_q(contact):
    covered = Q(pk__in=[])
    rows = list(contact.coverage.all())
    types = [row.machine_type_id for row in rows if row.kind == "machine_type"]
    rooms = [row.room_id for row in rows if row.kind == "room"]
    if types:
        covered |= Q(subject_type="machine", machine__machine_type_id__in=types)
    if any(row.kind == "inventory" for row in rows):
        covered |= Q(subject_type__in=INVENTORY_SUBJECTS)
    if rooms:
        covered |= Q(subject_type="bookable_space", space_id__in=rooms)
    return covered


def visible_work_orders(actor, space):
    from apps.machines.access import scope_machines_for_actor
    from apps.machines.models import Machine
    from apps.maintenance.models import WorkOrder
    live = work_order_areas(space)
    allowed = Q(pk__in=[])
    if areas.MACHINES in live and rbac.can(actor, Action.MANAGE_MACHINES, space.pk):
        machines = scope_machines_for_actor(actor, Machine.objects.filter(makerspace=space)).values("pk")
        allowed |= Q(subject_type="machine", machine_id__in=machines)
    if areas.INVENTORY in live and rbac.can(actor, Action.EDIT_INVENTORY, space.pk):
        allowed |= Q(subject_type__in=INVENTORY_SUBJECTS)
    if areas.ROOMS in live and rbac.can(actor, Action.MANAGE_BOOKINGS, space.pk):
        allowed |= Q(subject_type="bookable_space")
    if rbac.can(actor, Action.WORK_REPAIRS, space.pk):
        allowed |= Q(assignee_id=actor.pk) | authority.assigned_q(actor, prefix="issue__")
    if rbac.can(actor, Action.RUN_MAINTENANCE, space.pk):
        contact = authority.contact_for(actor, space.pk)
        if contact is not None:
            allowed |= Q(schedule__isnull=False) & _coverage_q(contact)
    return WorkOrder.objects.filter(makerspace=space).filter(allowed & _area_q(live)).distinct()


def visible_issues(actor, space):
    return authority.visible_issues(actor, space)

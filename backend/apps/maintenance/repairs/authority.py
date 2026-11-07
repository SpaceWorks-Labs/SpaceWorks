"""Who may see and work an issue, run maintenance and set service state (#102, Q-T1 a).

Two kinds of authority, never mixed up:

* a MANAGER (#102) acts on everything in the area they manage -- `areas.manager_may`;
* a TECHNICIAN holds `work_repairs` / `run_maintenance` / `set_service_state` and acts
  only on the jobs assigned to them (repairs), and on the machine types, inventory and
  rooms their in-house contact's coverage names (maintenance and service state). No
  coverage means nothing beyond the assigned jobs: it fails closed, like a Machine
  Manager without type links.

Every query here is makerspace-scoped; rbac decides the actions.
"""

from django.db.models import Q

from apps.accounts import rbac

from . import areas

Action = rbac.Action


def contact_for(actor, space_id):
    from apps.maintenance.models import TechnicianContact
    if actor is None or not getattr(actor, "is_authenticated", False):
        return None
    return (TechnicianContact.objects.filter(makerspace_id=space_id, person_id=actor.pk, is_archived=False,
                                             kind=TechnicianContact.Kind.IN_HOUSE)
            .prefetch_related("coverage").first())


def covers(contact, subject_type, subject):
    if contact is None or subject is None:
        return False
    rows = list(contact.coverage.all())
    if subject_type == "machine":
        return any(row.kind == "machine_type" and row.machine_type_id == subject.machine_type_id for row in rows)
    if subject_type in ("inventory_product", "inventory_asset"):
        return any(row.kind == "inventory" for row in rows)
    return any(row.kind == "room" and row.room_id == subject.pk for row in rows)


def technician_covers(actor, space_id, action, subject_type, subject):
    return rbac.can(actor, action, space_id) and covers(contact_for(actor, space_id), subject_type, subject)


def may_act_on_subject(actor, space_id, action, subject_type, subject):
    """Maintenance runs and service state: the area manager, or a covering Technician."""
    return (areas.manager_may(actor, space_id, subject_type, subject)
            or technician_covers(actor, space_id, action, subject_type, subject))


def assigned_q(actor, prefix=""):
    return Q(**{f"{prefix}assignments__person_id": actor.pk}) | Q(**{
        f"{prefix}assignments__contact__person_id": actor.pk,
        f"{prefix}assignments__contact__is_archived": False})


def is_assigned(actor, issue):
    from apps.maintenance.models import IssueReport
    return IssueReport.objects.filter(pk=issue.pk).filter(assigned_q(actor)).exists()


def manages_issue(actor, issue):
    return areas.manager_may(actor, issue.makerspace_id, issue.subject_type, issue.subject)


def works_issue(actor, issue):
    """A Technician on a job assigned to them, while that area's repairs are on."""
    return (rbac.can(actor, Action.WORK_REPAIRS, issue.makerspace_id)
            and areas.on(issue.makerspace, areas.REPAIRS[issue.area]) and is_assigned(actor, issue))


def visible_issues(actor, space):
    """Issues this actor may read in one space: their areas as a manager, plus own jobs."""
    from apps.machines.access import scope_machines_for_actor
    from apps.machines.models import Machine
    from apps.maintenance.models import IssueReport
    allowed = Q(pk__in=[])
    live = [area for area in areas.AREAS if areas.area_on(space, area)]
    if areas.MACHINES in live and rbac.can(actor, Action.MANAGE_MACHINES, space.pk):
        machines = scope_machines_for_actor(actor, Machine.objects.filter(makerspace=space)).values("pk")
        allowed |= Q(area=areas.MACHINES, machine_id__in=machines)
    if areas.INVENTORY in live and rbac.can(actor, Action.EDIT_INVENTORY, space.pk):
        allowed |= Q(area=areas.INVENTORY)
    if areas.ROOMS in live and rbac.can(actor, Action.MANAGE_BOOKINGS, space.pk):
        allowed |= Q(area=areas.ROOMS)
    repairs_live = [area for area in live if areas.on(space, areas.REPAIRS[area])]
    if repairs_live and rbac.can(actor, Action.WORK_REPAIRS, space.pk):
        allowed |= Q(area__in=repairs_live) & assigned_q(actor)
    active_repairs = Q(area__in=repairs_live) | Q(work_order__isnull=True)
    return IssueReport.objects.filter(makerspace=space).filter(allowed & active_repairs).distinct()


def technician_on_machine(actor, machine):
    """The maintenance-log seam (`services_shared.prepare_machine`): a covering Technician
    running maintenance, or one working an open repair on this very machine."""
    from apps.maintenance.models import IssueReport
    space_id = machine.makerspace_id
    if technician_covers(actor, space_id, Action.RUN_MAINTENANCE, "machine", machine):
        return True
    if not rbac.can(actor, Action.WORK_REPAIRS, space_id):
        return False
    return IssueReport.objects.filter(makerspace_id=space_id, machine_id=machine.pk,
                                      state__in=IssueReport.OPEN_STATES).filter(assigned_q(actor)).exists()


def technician_may_work_order(actor, order):
    """The work-order seam (`work_orders.may_manage`): a Technician assigned to the order
    or to the issue it carries, or covering the subject of a scheduled maintenance order."""
    space_id = order.makerspace_id
    if order.pk is None:
        return False  # opening work orders stays with the managers
    if rbac.can(actor, Action.WORK_REPAIRS, space_id):
        if order.assignee_id == actor.pk:
            return True
        issue = getattr(order, "issue", None)
        if issue is not None and is_assigned(actor, issue):
            return True
    return bool(order.schedule_id) and technician_covers(
        actor, space_id, Action.RUN_MAINTENANCE, order.subject_type, order.subject)

"""Decision 242(n): the work orders a Technician may read.

`views_work_orders.visible` scoped every subject through manager authority, so an order assigned to a
Technician, or carried by an issue assigned to them, never appeared and `technician_may_work_order`
was unreachable. This builds the extra `Q` for a holder of `work_repairs` (assigned work) and
`run_maintenance` (scheduled orders on machines of a covered type). Everything stays inside one space;
a person without a coverage row gets nothing beyond their assigned jobs (fail closed).
"""

from django.db.models import Q

from apps.accounts import rbac
from apps.maintenance.repairs import authority


def technician_q(actor, space):
    allowed = Q(pk__in=[])
    if rbac.can(actor, rbac.Action.WORK_REPAIRS, space.pk):
        allowed |= Q(assignee_id=actor.pk)
        allowed |= Q(issue__assignments__person_id=actor.pk)
        allowed |= Q(issue__assignments__contact__person_id=actor.pk, issue__assignments__contact__is_archived=False)
    if rbac.can(actor, rbac.Action.RUN_MAINTENANCE, space.pk):
        contact = authority.contact_for(actor, space.pk)
        if contact is not None:
            type_ids = [row.machine_type_id for row in contact.coverage.all() if row.kind == "machine_type"]
            if type_ids:
                allowed |= Q(subject_type="machine", schedule__isnull=False, machine__machine_type_id__in=type_ids)
    return allowed

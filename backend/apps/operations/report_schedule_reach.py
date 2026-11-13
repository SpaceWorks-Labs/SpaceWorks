"""Whose reach a scheduled report carries, and who may see or receive it.

A schedule's file is built with its CREATOR's authority (``report_schedule_services``), and
many builders narrow rows by that actor: machine reports by machine type, audit reports by
area (#219e), repairs by subject and coverage, loan-context reports by event/booking grant,
finance by domain. Holding the report's ``required_action`` is therefore not enough to read
someone else's file. Two rules follow (API role-scoping audit, release 0.12.0):

* A schedule is listed, edited, deleted and run only by its creator or the space's Space
  Manager (MANAGE_MAKERSPACE; the superadmin through rbac).
* A local recipient of an actor-narrowed report gets the file only when their own reach
  covers the creator's: the creator, the Space Manager, or (for action/type-narrowed keys)
  someone holding every effective action the creator holds here with machine-type reach at
  least as wide. Grant- and coverage-narrowed keys go to the creator and Space Manager only.
"""

from django.db.models import Q

from apps.accounts import rbac

_ACTION_NARROWED = frozenset({
    "consumable-usage", "consumable-pools", "procurement-performance", "overdue-loans", "longest-loans",
    "qr-scan-actors", "certification-coverage", "member-retention", "membership-revenue", "membership-growth",
    "payments-ageing", "revenue-over-time", "cash-book", "payment-reconciliation", "refunds",
    "booking-top-members", "presence-top-visitors", "printer-service",
})


def _key_sets():
    from .report_definitions_audit import AUDIT_VIEWER_REPORT_KEYS
    from .report_definitions_finance_l5 import L5_ACTOR_REPORT_KEYS
    from .report_definitions_loan_context import LOAN_CONTEXT_REPORT_KEYS
    from .report_definitions_machines import MACHINE_REPORT_KEYS
    from .report_definitions_repairs import REPAIRS_REPORT_KEYS
    strict = AUDIT_VIEWER_REPORT_KEYS | {"audit-top-actors"} | LOAN_CONTEXT_REPORT_KEYS | REPAIRS_REPORT_KEYS
    return strict, _ACTION_NARROWED | MACHINE_REPORT_KEYS | L5_ACTOR_REPORT_KEYS


def manageable(user, queryset):
    """Schedules ``user`` created, plus every schedule of a space they manage."""
    managed = rbac.makerspaces_for_action(user, rbac.Action.MANAGE_MAKERSPACE)
    if managed is rbac.ALL:
        return queryset
    return queryset.filter(Q(created_by_id=user.pk) | Q(makerspace_id__in=managed or []))


def _machine_reach_covers(user, creator, makerspace_id):
    from apps.machines import role_scope
    wide, narrow = role_scope.manage_scope_for(user, makerspace_id), role_scope.manage_scope_for(creator, makerspace_id)
    if wide is role_scope.EXEMPT:
        return True
    if narrow is role_scope.EXEMPT:
        return False
    return all(set(n) <= set(w) for w, n in zip(wide, narrow))


def _coverage_covers(user, creator, makerspace_id):
    """A Technician creator's coverage (machine types, rooms, inventory) must be covered by the recipient's.

    Action sets alone cannot tell two Technicians apart (open item B4): their reach is the in-house
    contact's coverage rows, compared here exactly like machine-type reach for a manager.
    """
    from apps.maintenance.repairs.authority import contact_for

    def signature(person):
        contact = contact_for(person, makerspace_id)
        return set() if contact is None else {
            (row.kind, row.machine_type_id or row.room_id or 0) for row in contact.coverage.all()}
    return signature(creator) <= signature(user)


def recipient_reaches(user, schedule, definition):
    """Whether a local staff recipient may receive this schedule's file."""
    strict, narrowed = _key_sets()
    if definition.key not in strict | narrowed:
        return True
    creator, space_id = schedule.created_by, schedule.makerspace_id
    if (creator is not None and user.pk == creator.pk) or rbac.can(user, rbac.Action.MANAGE_MAKERSPACE, space_id):
        return True
    if creator is None or definition.key in strict:
        return False
    if not rbac.effective_actions(creator, space_id) <= rbac.effective_actions(user, space_id):
        return False
    if rbac.can(creator, rbac.Action.MANAGE_MACHINES, space_id) and not _machine_reach_covers(
            user, creator, space_id):
        return False
    return _coverage_covers(user, creator, space_id)

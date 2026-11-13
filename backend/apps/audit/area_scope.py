"""Narrow audit rows to the areas a reader works in (owner decision 219(e)).

The superadmin and a space's Space Manager (MANAGE_MAKERSPACE) keep the whole space.
Every other audit reader -- a VIEW_AUDIT holder, or since #219(e-1) a holder of any
``areas.READER_ACTIONS`` action without VIEW_AUDIT -- reads, per space, only rows whose
action belongs to an area their effective actions open there (``areas.AREA_ACTIONS``).
Only the audit log, its saved views and the audit reports admit the second kind of
reader; every other VIEW_AUDIT check is unchanged. Repair rows are split
by subject: issue and work-order rows follow the repairs authority itself
(``report_scope.visible_issues`` / ``visible_work_orders``, so a type-scoped Machine
Manager and a Technician's own jobs carry over); the other repair rows follow their
recorded ``area`` / ``subject_type`` metadata, and a row with neither fails closed.

Callers apply this AFTER the audit-reader tenant scope (``scope_audit_tenants``); it
never widens one.
"""

from django.apps import apps as django_apps
from django.db.models import CharField, Q
from django.db.models.functions import Cast

from apps.accounts import rbac

from . import areas

ISSUE_TARGET, WORK_ORDER_TARGET = "maintenance.issuereport", "maintenance.workorder"
SUBJECT_TYPES = {"machines": ("machine",), "inventory": ("inventory_product", "inventory_asset"),
                 "rooms": ("bookable_space",)}
COVERAGE_AREAS = {"machine_type": "machines", "inventory": "inventory", "room": "rooms"}
_NONE = Q(pk__in=[])


def _namespace_q(name):
    return Q(action=name) | Q(action__startswith=f"{name}.")


def area_q(wanted):
    """Rows whose action is PLACED in any of ``wanted``; the SQL twin of ``areas_for_action``."""
    wanted = set(wanted)
    q = Q(action__in=sorted(a for a, owners in areas.EXACT_AREAS.items() if wanted & set(owners)))
    for name, owners in areas.NAMESPACE_AREAS.items():
        if wanted & set(owners):
            overridden = sorted(a for a in areas.EXACT_AREAS if areas.namespace(a) == name)
            q |= _namespace_q(name) & ~Q(action__in=overridden) if overridden else _namespace_q(name)
    if areas.PLATFORM in wanted:
        known = Q(action__in=sorted(areas.EXACT_AREAS))
        for name in areas.NAMESPACE_AREAS:
            known |= _namespace_q(name)
        q |= ~known
    return q


def _subject_areas(actor, space, actions):
    subject = {area for area, needed in areas.REPAIR_SUBJECT_ACTIONS.items() if needed in actions}
    if set(areas.TECHNICIAN_ACTIONS) & actions:
        from apps.maintenance.repairs.authority import contact_for
        contact = contact_for(actor, space.pk)
        if contact is not None:
            subject |= {COVERAGE_AREAS[row.kind] for row in contact.coverage.all() if row.kind in COVERAGE_AREAS}
        from apps.maintenance.repairs.authority import membership_reach
        if any(membership_reach(actor, space.pk)):
            subject.add(areas.MACHINES)  # machines/types linked on the staff row itself
    return subject


def _repairs_q(actor, space, actions):
    relevant = set(areas.REPAIR_SUBJECT_ACTIONS.values()) | set(areas.TECHNICIAN_ACTIONS)
    if not django_apps.is_installed("apps.maintenance") or not relevant & actions:
        return _NONE
    from apps.maintenance.repairs.report_scope import visible_issues, visible_work_orders

    def ids(rows):
        return rows.annotate(audit_target=Cast("pk", output_field=CharField())).values("audit_target")

    subject = _subject_areas(actor, space, actions)
    # Machine rows are never matched by subject type alone (every Machine Manager would read every
    # type's repairs): they must name a machine the reader reaches, via `meta.machine_id`.
    other = subject - {areas.MACHINES}
    by_subject = Q(meta__area__in=sorted(other)) | Q(
        meta__subject_type__in=[kind for area in sorted(other) for kind in SUBJECT_TYPES[area]])
    if areas.MACHINES in subject:
        from .area_scope_machines import repair_machines_q
        by_subject |= repair_machines_q(actor, space)
    targeted = (Q(target_type=ISSUE_TARGET, target_id__in=ids(visible_issues(actor, space)))
                | Q(target_type=WORK_ORDER_TARGET, target_id__in=ids(visible_work_orders(actor, space))))
    untargeted = ~Q(target_type__in=(ISSUE_TARGET, WORK_ORDER_TARGET)) & by_subject
    return area_q({areas.REPAIRS}) & (targeted | untargeted)


def _space_q(actor, space):
    actions = rbac.effective_actions(actor, space.pk)
    held = areas.areas_for_actions(actions)
    if areas.PLATFORM in held:
        return Q()
    q = area_q(held - {areas.MACHINES}) | _repairs_q(actor, space, actions)
    if areas.MACHINES in held:
        # Per-type reach: a type-scoped Machine Manager reads only their types' rows.
        from .area_scope_machines import machines_q
        q |= machines_q(actor, space, area_q({areas.MACHINES}))
    return q


def audit_reader_spaces(actor):
    """Spaces whose audit log the actor reads: VIEW_AUDIT or an area reader action (#219 e-1)."""
    return rbac.makerspaces_for_actions(actor, rbac.Action.VIEW_AUDIT, *areas.READER_ACTIONS)


def can_read_audit(actor, makerspace_id):
    """Single-space twin of ``audit_reader_spaces``."""
    return any(rbac.can(actor, action, makerspace_id)
               for action in (rbac.Action.VIEW_AUDIT, *areas.READER_ACTIONS))


def scope_audit_tenants(actor, queryset, field="makerspace_id"):
    """The tenant half of audit reading; ``scope_audit_rows`` then narrows by area."""
    spaces = audit_reader_spaces(actor)
    if spaces is rbac.ALL:
        return queryset
    return queryset.filter(**{f"{field}__in": spaces}) if spaces else queryset.none()


def scope_audit_rows(actor, queryset):
    """Keep only rows of the reader's areas, space by space; superadmin is unchanged."""
    if rbac._is_superadmin(actor):
        return queryset
    from apps.makerspaces.models import Makerspace
    spaces = audit_reader_spaces(actor)
    if spaces is rbac.ALL:
        return queryset
    allowed = _NONE
    for space in Makerspace.objects.filter(pk__in=spaces).order_by("pk"):
        allowed |= Q(makerspace_id=space.pk) & _space_q(actor, space)
    return queryset.filter(allowed)


def makerspaces_for_area(actor, area):
    """VIEW_AUDIT spaces where ``area`` is open to the reader (ALL for the superadmin)."""
    spaces = rbac.makerspaces_for_action(actor, rbac.Action.VIEW_AUDIT)
    if spaces is rbac.ALL or rbac._is_superadmin(actor):
        return spaces
    return {pk for pk in spaces if area in areas.areas_for_actions(rbac.effective_actions(actor, pk))}

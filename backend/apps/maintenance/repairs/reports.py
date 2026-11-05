"""The repairs report family (RP-5): open work orders, technician workload, repair time
per area and parts used.

Every builder is tenant-local and narrows its rows to the viewer (`report_scope`), so a
Machine Manager sees only their machine types and a Technician only their own jobs. No
viewer means no rows: the family is never scheduled or aggregated across spaces.
"""

from collections import defaultdict
from statistics import median

from django.utils import timezone

from apps.operations.report_types import ReportResult

from . import report_scope
from .areas import SUBJECT_AREA
from .report_fields import PARTS_FIELDS, REPAIR_TIME_FIELDS, WORK_ORDER_FIELDS, WORKLOAD_FIELDS


def _space(makerspace_id):
    from apps.makerspaces.models import Makerspace
    return Makerspace.objects.get(pk=makerspace_id)


def _in_range(value, date_range):
    if value is None:
        return False
    start, end = date_range or (None, None)
    return (start is None or value >= start) and (end is None or value < end)


def _range_q(field, date_range):
    from django.db.models import Q
    start, end = date_range or (None, None)
    q = Q()
    if start is not None:
        q &= Q(**{f"{field}__gte": start})
    if end is not None:
        q &= Q(**{f"{field}__lt": end})
    return q


def _limited(records, limit):
    return records[:limit] if limit is not None else records


def build_work_orders(makerspace_id, *, limit=None, date_range=None, actor=None):
    """A snapshot of the open work orders now; overdue ones (past `due_on`) first."""
    from apps.maintenance.models import WorkOrder
    if actor is None:
        return ReportResult(WORK_ORDER_FIELDS, [])
    today, now = timezone.localdate(), timezone.now()
    orders = (report_scope.visible_work_orders(actor, _space(makerspace_id))
              .filter(status__in=WorkOrder.OPEN_STATUSES)
              .select_related("machine__machine_type", "product", "asset", "space", "issue"))
    records = []
    for order in orders:
        issue = getattr(order, "issue", None)  # the reverse one-to-one: absent for maintenance
        records.append({
            "work_order_id": order.pk, "area": SUBJECT_AREA[order.subject_type], "subject_type": order.subject_type,
            "subject_name": str(order.subject) if order.subject is not None else "",
            "machine_type": order.machine.machine_type.name if order.machine_id else None,
            "title": order.title, "priority": order.priority, "status": order.status, "due_on": order.due_on,
            "overdue": bool(order.due_on and order.due_on < today),
            "days_open": (now - order.created_at).days, "assigned": order.assignee_id is not None,
            "issue_id": getattr(issue, "pk", None), "created_at": order.created_at,
        })
    records.sort(key=lambda row: (not row["overdue"], row["due_on"] is None, row["due_on"] or today,
                                  row["created_at"]))
    return ReportResult(WORK_ORDER_FIELDS, _limited(records, limit))


def _party(assignment):
    if assignment.contact_id:
        contact = assignment.contact
        return ("contact", contact.pk), contact.name, contact.kind
    person = assignment.person
    label = (person.first_name or "").strip() or f"Staff member {person.pk}"
    return ("person", person.pk), label, "staff"


def build_technician_workload(makerspace_id, *, limit=None, date_range=None, actor=None):
    """Per technician (a contact, or a person who took the job): open, started, overdue, fixed."""
    from apps.maintenance.models import IssueAssignment, IssueReport
    if actor is None:
        return ReportResult(WORKLOAD_FIELDS, [])
    today = timezone.localdate()
    issues = report_scope.visible_issues(actor, _space(makerspace_id)).values("pk")
    rows = {}
    assignments = (IssueAssignment.objects.filter(issue_id__in=issues)
                   .select_related("issue__work_order", "contact", "person"))
    for assignment in assignments:
        key, label, kind = _party(assignment)
        row = rows.setdefault(key, {"technician": label, "technician_kind": kind, "open_jobs": 0,
                                    "in_progress": 0, "overdue": 0, "fixed_in_period": 0})
        issue = assignment.issue
        if issue.state in IssueReport.OPEN_STATES:
            row["open_jobs"] += 1
            row["in_progress"] += issue.state == IssueReport.State.IN_PROGRESS
            order = issue.work_order
            row["overdue"] += bool(order is not None and order.due_on and order.due_on < today)
        if _in_range(issue.fixed_at, date_range):
            row["fixed_in_period"] += 1
    records = sorted(rows.values(), key=lambda row: (-row["open_jobs"], -row["overdue"], row["technician"]))
    return ReportResult(WORKLOAD_FIELDS, _limited(records, limit))


def build_repair_time(makerspace_id, *, limit=None, date_range=None, actor=None):
    """Per area (machines also per type): reported and fixed in the period, open now, and the
    average and median hours from report to fix for the issues fixed in the period."""
    from apps.maintenance.models import IssueReport
    if actor is None:
        return ReportResult(REPAIR_TIME_FIELDS, [])
    groups = defaultdict(lambda: {"reported": 0, "fixed": 0, "open": 0, "hours": []})
    issues = report_scope.visible_issues(actor, _space(makerspace_id)).select_related("machine__machine_type")
    for issue in issues:
        group = groups[(issue.area, issue.machine.machine_type.name if issue.machine_id else None)]
        group["reported"] += _in_range(issue.created_at, date_range)
        group["open"] += issue.state in IssueReport.OPEN_STATES
        if _in_range(issue.fixed_at, date_range):
            group["fixed"] += 1
            group["hours"].append((issue.fixed_at - issue.created_at).total_seconds() / 3600)
    records = [{
        "area": area, "machine_type": machine_type, "reported": group["reported"], "fixed": group["fixed"],
        "open": group["open"],
        "average_hours_to_fix": round(sum(group["hours"]) / len(group["hours"]), 2) if group["hours"] else None,
        "median_hours_to_fix": round(median(group["hours"]), 2) if group["hours"] else None,
    } for (area, machine_type), group in groups.items()]
    records.sort(key=lambda row: (row["area"], row["machine_type"] or ""))
    return ReportResult(REPAIR_TIME_FIELDS, _limited(records, limit))


def build_parts_used(makerspace_id, *, limit=None, date_range=None, actor=None):
    """Parts recorded on visible repair jobs in the period: used (out of stock) and needed."""
    from apps.maintenance.models import RepairPart
    if actor is None:
        return ReportResult(PARTS_FIELDS, [])
    issues = report_scope.visible_issues(actor, _space(makerspace_id)).values("pk")
    parts = (RepairPart.objects.filter(issue_id__in=issues).filter(_range_q("created_at", date_range))
             .select_related("issue"))
    groups = {}
    for part in parts:
        key = (part.issue.area, part.kind, part.product_id, part.name)
        row = groups.setdefault(key, {"area": part.issue.area, "kind": part.kind, "part": part.name,
                                      "product_id": part.product_id, "quantity": 0, "issues": set(),
                                      "last_recorded_at": part.created_at})
        row["quantity"] += part.quantity
        row["issues"].add(part.issue_id)
        row["last_recorded_at"] = max(row["last_recorded_at"], part.created_at)
    records = [{**row, "issues": len(row["issues"])} for row in groups.values()]
    records.sort(key=lambda row: (row["kind"] != "used", -row["quantity"], row["part"]))
    return ReportResult(PARTS_FIELDS, _limited(records, limit))

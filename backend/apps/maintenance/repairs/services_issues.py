"""The issue lifecycle: report, triage, reject, assign, start, fix, close (#103, #102, C-3).

reported -> triaged -> assigned -> in_progress -> fixed -> closed, or -> rejected.

* Reporting needs the area's `*.issue_reporting` switch; everything after the report
  needs `*.repairs`, except that a manager may still fix, close or reject a notify-only
  report (#102: managers act themselves).
* Triage with repairs on opens L12's work order for the subject and links it; starting
  and fixing the issue move that work order (its own state machine, called, never
  copied), so a fixed machine repair also writes the machine's maintenance log.
* A Technician works only the jobs assigned to them (`authority.works_issue`).
"""

from django.utils.translation import gettext
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.maintenance import work_orders

from . import areas, authority, errors, history, notify, photos


def _states():
    from apps.maintenance.models import IssueReport
    return IssueReport.State


def _require_manager(actor, issue):
    if not authority.manages_issue(actor, issue):
        raise PermissionDenied()


def _require_worker(actor, issue):
    if authority.manages_issue(actor, issue):
        return "manager"
    if authority.works_issue(actor, issue):
        return "technician"
    raise PermissionDenied()


def _expect(issue, *states):
    if issue.state not in states:
        raise errors.bad_state(f"A {issue.state} issue cannot do that.")


def _subject_fields(subject_type, subject):
    fields = {areas.SUBJECT_FIELD[subject_type]: subject}
    if subject_type == "inventory_asset":
        fields["product"] = subject.product
    return fields


# A source names the origin FK it fills; only a session's differs from its source name.
ORIGIN_FIELDS = {"session": "machine_session"}


def file_report(space, *, reporter, source, origin, subject_type, subject, title, description, validated,
                reporter_name="", reporter_email=""):
    """A member's or an account-less borrower's report (eligibility already proven)."""
    from apps.maintenance.models import IssueReport
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    area = areas.SUBJECT_AREA[subject_type]
    areas.require(space, areas.REPORTING[area])
    if getattr(subject, "makerspace_id", space.pk) != space.pk:
        raise errors.not_eligible()
    with transaction.atomic():
        assert_write_allowed(space.pk)
        issue = IssueReport.objects.create(
            makerspace=space, area=area, subject_type=subject_type, source=source, reporter=reporter,
            reporter_name=str(reporter_name or "")[:200], reporter_email=str(reporter_email or "")[:254],
            title=str(title).strip()[:200], description=str(description).strip()[:4000],
            **{ORIGIN_FIELDS.get(source, source): origin}, **_subject_fields(subject_type, subject))
        photos.attach(issue, validated, "reported", reporter)
        history.step(issue, "reported", reporter, "issue.reported",
                     meta={"source": source, "subject_type": subject_type, "photos": len(validated)})
        notify.staff(issue, "issue_reported")
    return issue


@transaction.atomic
def open_issue(actor, space, *, subject_type, subject, title, description="", priority="normal"):
    """Staff open a repair job themselves (no reporter); it starts triaged."""
    from apps.maintenance.models import IssueReport
    area = areas.SUBJECT_AREA[subject_type]
    areas.require(space, areas.REPAIRS[area])
    if subject.makerspace_id != space.pk:
        raise ValidationError({"subject_id": gettext("The subject must belong to this makerspace.")})
    if not areas.manager_may(actor, space.pk, subject_type, subject):
        raise errors.out_of_scope()
    issue = IssueReport.objects.create(
        makerspace=space, area=area, subject_type=subject_type, source="staff", title=str(title).strip()[:200],
        description=str(description or "").strip()[:4000], priority=priority, state=_states().TRIAGED,
        **_subject_fields(subject_type, subject))
    issue.work_order = work_orders.create_work_order(
        actor, space, subject_type=subject_type, subject=subject, title=issue.title,
        description=issue.description, priority=priority)
    issue.save(update_fields=["work_order", "updated_at"])
    history.step(issue, "triaged", actor, "issue.opened",
                 meta={"subject_type": subject_type, "work_order_id": issue.work_order_id})
    return issue


@transaction.atomic
def triage(actor, issue, *, priority=None, note=""):
    issue = history.lock(issue)
    _require_manager(actor, issue)
    _expect(issue, _states().REPORTED)
    if priority:
        issue.priority = priority
    if areas.on(issue.makerspace, areas.REPAIRS[issue.area]):
        issue.work_order = work_orders.create_work_order(
            actor, issue.makerspace, subject_type=issue.subject_type, subject=issue.subject, title=issue.title,
            description=issue.description, priority=issue.priority)
    issue.state = _states().TRIAGED
    issue.save(update_fields=["state", "priority", "work_order", "updated_at"])
    history.step(issue, "triaged", actor, "issue.triaged", note=note,
                 meta={"work_order_id": issue.work_order_id, "priority": issue.priority})
    return issue


def _order(issue):
    from apps.maintenance.models import WorkOrder
    if issue.work_order_id is None:
        return None
    return WorkOrder.objects.get(pk=issue.work_order_id)


def _move_order(actor, issue, target, resolution=""):
    order = _order(issue)
    if order is None or order.status in ("done", "cancelled") or order.status == target:
        return
    if target == "done" and order.status != "in_progress":
        order = work_orders.move(actor, order, "in_progress")
    work_orders.move(actor, order, target, resolution=resolution)


@transaction.atomic
def reject(actor, issue, *, reason):
    issue = history.lock(issue)
    _require_manager(actor, issue)
    S = _states()
    _expect(issue, S.REPORTED, S.TRIAGED, S.ASSIGNED, S.IN_PROGRESS)
    reason = str(reason or "").strip()
    if not reason:
        raise ValidationError({"reason": gettext("Say why the issue is rejected.")})
    _move_order(actor, issue, "cancelled", reason)
    issue.state, issue.resolution, issue.closed_at = S.REJECTED, reason[:4000], timezone.now()
    issue.save(update_fields=["state", "resolution", "closed_at", "updated_at"])
    history.step(issue, "rejected", actor, "issue.rejected", note=reason)
    notify.loan_borrower_repair(issue, "rejected")  # a loan handoff's borrower; no-op otherwise
    return issue


@transaction.atomic
def assign(actor, issue, *, contact=None, myself=False):
    from apps.maintenance.models import IssueAssignment
    issue = history.lock(issue)
    _require_manager(actor, issue)
    areas.require(issue.makerspace, areas.REPAIRS[issue.area])
    S = _states()
    _expect(issue, S.TRIAGED, S.ASSIGNED, S.IN_PROGRESS)
    if (contact is None) == (not myself):
        raise ValidationError({"contact_id": gettext("Assign one technician, or yourself.")})
    if contact is not None and (contact.makerspace_id != issue.makerspace_id or contact.is_archived):
        raise ValidationError({"contact_id": gettext("Choose a technician of this makerspace.")})
    row, created = IssueAssignment.objects.get_or_create(
        issue=issue, **({"contact": contact} if contact is not None else {"person": actor}))
    person = actor if myself else getattr(contact, "person", None)
    _sync_assignee(actor, issue, person)
    if issue.state == S.TRIAGED:
        issue.state = S.ASSIGNED
        issue.save(update_fields=["state", "updated_at"])
    if created:
        history.step(issue, "assigned", actor, "issue.assigned", contact=contact,
                     meta={"assignment_id": row.pk, "self_assigned": bool(myself),
                           "contact_id": getattr(contact, "pk", None)})
    return issue


def _sync_assignee(actor, issue, person):
    order = _order(issue)
    if order is None or person is None or order.assignee_id or order.status not in ("open", "in_progress",
                                                                                       "on_hold"):
        return
    try:
        work_orders.assign(actor, order, person)
    except ValidationError:
        pass  # a contact whose person holds no staff action stays on the issue only


@transaction.atomic
def unassign(actor, issue, assignment_id):
    from apps.maintenance.models import IssueAssignment
    issue = history.lock(issue)
    _require_manager(actor, issue)
    row = IssueAssignment.objects.filter(issue=issue, pk=assignment_id).first()
    if row is None:
        raise ValidationError({"assignment_id": gettext("That assignment is not on this issue.")})
    contact, row_id = row.contact, row.pk
    row.delete()
    history.step(issue, "unassigned", actor, "issue.unassigned", contact=contact,
                 meta={"assignment_id": row_id})
    return issue


@transaction.atomic
def start(actor, issue):
    issue = history.lock(issue)
    _require_worker(actor, issue)
    S = _states()
    _expect(issue, S.TRIAGED, S.ASSIGNED)
    _move_order(actor, issue, "in_progress")
    issue.state = S.IN_PROGRESS
    issue.save(update_fields=["state", "updated_at"])
    history.step(issue, "started", actor, "repair.started")
    return issue


def fix(actor, issue, *, resolution, photo_tokens=(), owner=None):
    validated = photos.validate(issue.makerspace, photo_tokens, owner) if photo_tokens else []
    with transaction.atomic():
        issue = history.lock(issue)
        _require_worker(actor, issue)
        S = _states()
        _expect(issue, S.REPORTED, S.TRIAGED, S.ASSIGNED, S.IN_PROGRESS)
        resolution = str(resolution or "").strip()
        if not resolution:
            raise ValidationError({"resolution": gettext("Say what was fixed.")})
        _move_order(actor, issue, "done", resolution)
        photos.attach(issue, validated, "fixed", actor)
        issue.state, issue.resolution, issue.fixed_at = S.FIXED, resolution[:4000], timezone.now()
        told_reporter = issue.source != "staff" and notify.reporter_fixed(issue)
        told_borrower = notify.loan_borrower_repair(issue, "fixed")  # a different person from the reporter
        if told_reporter or told_borrower:
            issue.reporter_notified_at = timezone.now()
        issue.save(update_fields=["state", "resolution", "fixed_at", "reporter_notified_at", "updated_at"])
        history.step(issue, "fixed", actor, "repair.fixed", note=resolution,
                     meta={"photos": len(validated), "reporter_notified": bool(issue.reporter_notified_at)})
    return issue


@transaction.atomic
def close(actor, issue, *, note=""):
    issue = history.lock(issue)
    _require_manager(actor, issue)
    _expect(issue, _states().FIXED)
    issue.state, issue.closed_at = _states().CLOSED, timezone.now()
    issue.save(update_fields=["state", "closed_at", "updated_at"])
    history.step(issue, "closed", actor, "issue.closed", note=note)
    return issue

"""Maintenance under each parent (#128 C-9): items and units, and rooms.

`machines.maintenance` keeps L12's machine schedules and logs unchanged. This adds the
same recurring schedule and append-only log for an inventory item or unit
(`inventory.maintenance`) and a bookable room (`bookings.room_maintenance`).

Managers keep schedules in their area (#102). Running one -- the log entry that moves
the next due date on by its interval -- is open to the manager and to a Technician
holding `run_maintenance` whose coverage names the subject (Q-T1 a). A Technician also
completes MACHINE schedules in their coverage, through the machine maintenance service.
"""

from django.utils.translation import gettext
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts import rbac
from apps.audit import services as audit

from . import areas, authority

FIELDS = {"inventory_product": "product", "inventory_asset": "asset", "bookable_space": "room"}


def _require_switch(space, subject_type):
    areas.require(space, areas.MAINTENANCE[areas.SUBJECT_AREA[subject_type]])


def _subject(row):
    return getattr(row, FIELDS[row.subject_type])


def _name(subject):
    return getattr(subject, "name", "") or getattr(subject, "asset_tag", "") or str(subject)


def _clean_interval(value):
    if type(value) is not int or not 1 <= value <= 3650:
        raise ValidationError({"interval_days": gettext("Use a whole number of days from 1 to 3650.")})
    return value


@transaction.atomic
def create_schedule(actor, space, *, subject_type, subject, description, interval_days, next_due):
    from apps.maintenance.models import SubjectMaintenanceSchedule
    if subject_type not in FIELDS:
        raise ValidationError({"subject_type": gettext("Items, units and rooms only; machines keep their own schedules.")})
    _require_switch(space, subject_type)
    if subject.makerspace_id != space.pk:
        raise ValidationError({"subject_id": gettext("The subject must belong to this makerspace.")})
    if not areas.manager_may(actor, space.pk, subject_type, subject):
        raise PermissionDenied()
    description = str(description or "").strip()
    if not description:
        raise ValidationError({"description": gettext("Describe the maintenance.")})
    row = SubjectMaintenanceSchedule.objects.create(
        makerspace=space, subject_type=subject_type, description=description[:2000],
        interval_days=_clean_interval(interval_days), next_due=next_due, **{FIELDS[subject_type]: subject})
    audit.record(actor, "maintenance.subject_schedule_created", makerspace=space, target=row,
                 meta={"schedule_id": row.pk, "subject_type": subject_type, f"{FIELDS[subject_type]}_id": subject.pk})
    return row


@transaction.atomic
def update_schedule(actor, schedule, *, description=None, interval_days=None, next_due=None, is_active=None):
    schedule = type(schedule).objects.select_for_update().select_related("makerspace").get(pk=schedule.pk)
    _require_switch(schedule.makerspace, schedule.subject_type)
    if not areas.manager_may(actor, schedule.makerspace_id, schedule.subject_type, _subject(schedule)):
        raise PermissionDenied()
    changed = []
    for name, value in (("description", description), ("next_due", next_due), ("is_active", is_active)):
        if value is not None:
            setattr(schedule, name, str(value).strip()[:2000] if name == "description" else value)
            changed.append(name)
    if interval_days is not None:
        schedule.interval_days = _clean_interval(interval_days)
        changed.append("interval_days")
    if changed:
        schedule.save(update_fields=[*changed, "updated_at"])
        audit.record(actor, "maintenance.subject_schedule_updated", makerspace=schedule.makerspace,
                     target=schedule, meta={"schedule_id": schedule.pk, "fields": sorted(changed)})
    return schedule


def _may_run(actor, space_id, subject_type, subject):
    return authority.may_act_on_subject(actor, space_id, rbac.Action.RUN_MAINTENANCE, subject_type, subject)


@transaction.atomic
def run(actor, schedule, *, summary, parts_note="", performed_at=None, cost=None, cost_method=None,
        cost_currency=None):
    """Log one run of a schedule and move its next due date on by the interval; a cost reaches the ledger."""
    from apps.maintenance.models import SubjectMaintenanceLog
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    assert_write_allowed(schedule.makerspace_id)
    schedule = type(schedule).objects.select_for_update().select_related("makerspace").get(pk=schedule.pk)
    _require_switch(schedule.makerspace, schedule.subject_type)
    subject = _subject(schedule)
    if not _may_run(actor, schedule.makerspace_id, schedule.subject_type, subject):
        raise PermissionDenied()
    if not schedule.is_active:
        raise ValidationError({"schedule": gettext("This schedule is inactive.")})
    summary = str(summary or "").strip()
    if not summary:
        raise ValidationError({"summary": gettext("Say what was done.")})
    performed_at = performed_at or timezone.now()
    log = SubjectMaintenanceLog.objects.create(
        makerspace=schedule.makerspace, schedule=schedule, subject_type=schedule.subject_type,
        performed_by=actor, performed_at=performed_at, summary=summary[:4000], parts_note=str(parts_note)[:2000],
        cost=cost, **{FIELDS[schedule.subject_type]: subject})
    from apps.maintenance.ledger import post_subject_log
    post_subject_log(actor, log, _name(subject), method=cost_method, currency=cost_currency)
    schedule.next_due = timezone.localdate(performed_at) + timedelta(days=schedule.interval_days)
    schedule.save(update_fields=["next_due", "updated_at"])
    audit.record(actor, "maintenance.subject_logged", makerspace=schedule.makerspace, target=log,
                 meta={"log_id": log.pk, "schedule_id": schedule.pk, "subject_type": schedule.subject_type})
    return log


def run_machine_schedule(actor, schedule, *, summary, parts_note="", cost=None, cost_method=None, cost_currency=None):
    """A Technician (or manager) completing a machine schedule: L12's own service."""
    from apps.maintenance.services_workflows import complete_due
    return complete_due(schedule, actor=actor, summary=summary, parts_note=parts_note, cost=cost,
                        cost_method=cost_method, cost_currency=cost_currency)


def visible_schedules(actor, space):
    """Item and room schedules this actor manages or covers, while their switch is on."""
    from apps.maintenance.models import SubjectMaintenanceSchedule
    live = {kind for kind in FIELDS if areas.on(space, areas.MAINTENANCE[areas.SUBJECT_AREA[kind]])}
    manages = {area: rbac.can(actor, areas.MANAGER_ACTION[area], space.pk) for area in (areas.INVENTORY, areas.ROOMS)}
    contact = (authority.contact_for(actor, space.pk)
               if rbac.can(actor, rbac.Action.RUN_MAINTENANCE, space.pk) else None)
    rows = SubjectMaintenanceSchedule.objects.filter(makerspace=space, subject_type__in=live).select_related(
        "product", "asset", "room").order_by("next_due", "id")[:500]
    return [row for row in rows if manages[areas.SUBJECT_AREA[row.subject_type]]
            or authority.covers(contact, row.subject_type, _subject(row))]

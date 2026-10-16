"""Maintenance adapters kept here so the equipment lane owns its source checks."""
from django.utils import timezone

from apps.accounts import rbac
from apps.hardware_requests.notifications_p2 import content, fanout, revision
from apps.integrations.destinations import NotificationScope
from apps.integrations.email_templates import render
from apps.integrations.email_templates_fablab import maintenance_context
from apps.integrations.notification_sources import NotificationSource, register_source
from apps.hardware_requests.notifications_p2 import safe_adapter
from apps.makerspaces.local_time import to_local
from .notifications_p2_certifications import staff_allowed

KIND = "machines.maintenance"


def version(row):
    return revision(row.pk, getattr(row, "updated_at", row.created_at), row.machine_id,
                    getattr(row, "next_due", ""), getattr(row, "meter_started_at", ""))


def eligible(envelope):
    from apps.maintenance.models import MaintenanceLog, MaintenanceSchedule
    model = MaintenanceSchedule if envelope.context["schedule"] else MaintenanceLog
    row = rbac.scope_notification_policy(model.objects.all(), makerspace_id=envelope.makerspace_id,
        field="machine__makerspace_id").select_related("machine__machine_type").filter(pk=envelope.source_id).first()
    if row is None or version(row) != envelope.revision or envelope.audience != "staff":
        return False
    if envelope.event in {"due_soon", "overdue"}:
        if not row.is_active:
            return False
        if envelope.context.get("meter"):
            from apps.maintenance.meters import meter_due
            if not meter_due(row):
                return False
        else:
            from apps.maintenance.reminders import reminder_time
            due = reminder_time(envelope.makerspace, row, envelope.event)
            if due is None or due > timezone.now():
                return False
            if envelope.event == "due_soon" and row.next_due < to_local(envelope.makerspace, timezone.now()).date():
                return False
    actor_id = envelope.context.get("actor_id")
    if actor_id:
        from apps.accounts.models import User
        from .access import can_manage_machine
        actor = User.objects.filter(pk=actor_id).first()
        if actor is None or not can_manage_machine(actor, row.machine):
            return False
    return staff_allowed(envelope, row.machine.machine_type_id)


@safe_adapter
def notify(instance, event_name, *, log_id=None, sync=False, due_reason=""):
    from apps.maintenance.models import MaintenanceSchedule
    is_schedule = isinstance(instance, MaintenanceSchedule)
    machine, space = instance.machine, instance.machine.makerspace
    log = None
    if log_id:
        from apps.maintenance.models import MaintenanceLog
        log = rbac.scope_notification_policy(MaintenanceLog.objects.all(),
            makerspace_id=space.pk, field="machine__makerspace_id").get(pk=log_id, machine=machine)
    if not is_schedule:
        log = instance
    context = maintenance_context(machine, event_name, schedule=instance if is_schedule else None,
                                  log=log, next_steps=due_reason)
    rendered = render(space, "maintenance", "staff", event_name, context, machine_type=machine.machine_type)
    if due_reason:
        rendered["text_body"] = due_reason + "\n\n" + rendered["text_body"]
    return fanout(space=space, feature="maintenance", stream="maintenance", event=event_name,
        kind=KIND, source=instance.pk, version=version(instance), subject=instance,
        staff=content(rendered), scope=NotificationScope(machine=machine),
        context={"schedule": is_schedule, "meter": bool(due_reason),
                 "machine_id": machine.pk,
                 "schedule_id": instance.pk if is_schedule else None,
                 "maintenance_log_id": log.pk if log else None,
                 "actor_id": (log.performed_by_id if log else getattr(instance, "created_by_id", None))})


def register():
    register_source(KIND, NotificationSource(eligible))

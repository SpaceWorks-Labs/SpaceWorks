"""Maintenance lockout (machines D6, MT5): an overdue blocking schedule stops new work.

A schedule marked `blocks_use` that is overdue past the type's grace days (the reminder
policy's `grace_days`, default 0) locks the machine: no job starts on it, and machine
sessions (L23) refuse it the same way. Inert while `machines.maintenance` is off or the
maintenance app is tombstoned. The lock clears itself when the schedule is completed.

`schedule_blocks` is the one rule. `blocking_schedules` feeds it live rows; the queue-ETA
snapshot (`lockout_batch.py`) feeds it rows and meter readings it loaded in bulk.

"Today" is the SPACE's local date (`makerspaces.local_time`), never the deployment's
timezone, in both feeds (decision 220(d)): a space far from the server must not lock or
unlock a day early near midnight.
"""

from datetime import timedelta

from rest_framework import status
from rest_framework.exceptions import APIException

FEATURE = "machines.maintenance"
METERS = "maintenance.meters"


class MachineLockedOut(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "machine_locked_out"

    def __init__(self, schedules):
        super().__init__({"detail": "Overdue safety maintenance blocks this machine.",
                          "code": "machine_locked_out", "schedule_ids": [row.pk for row in schedules]},
                         "machine_locked_out")


def lockout_active(makerspace):
    """Lockout applies only while the maintenance app ships and the space enabled the switch."""
    from apps.makerspaces.platform import feature_enabled
    from apps.separability.registry import runtime_active
    return runtime_active("maintenance") and feature_enabled(makerspace, FEATURE)


def meters_active(makerspace):
    from apps.makerspaces.platform import feature_enabled
    return feature_enabled(makerspace, METERS)


def schedule_blocks(row, today, grace_days, *, meters_on, reading):
    """Whether one loaded schedule locks its machine; issues no queries of its own.

    `maintenance.meters.due(row, today - grace)`: the calendar trigger blocks once overdue
    past the grace days; a usage meter (only while `maintenance.meters` is on) blocks once
    its hours or jobs threshold is reached. `reading()` returns `(hours, jobs)` and is
    called only when a meter can decide.
    """
    if not (row.is_active and row.blocks_use):
        return False
    if row.trigger in ("days", "both") and row.next_due <= today - timedelta(days=grace_days or 0):
        return True
    if row.trigger == "days" or not meters_on:
        return False
    hours, jobs = reading()
    return bool((row.usage_hours is not None and hours >= row.usage_hours)
                or (row.job_count is not None and jobs >= row.job_count))


def blocking_schedules(machine, *, today=None):
    if not lockout_active(machine.makerspace):
        return []
    from apps.maintenance.meters import readings
    from apps.maintenance.models import MaintenanceSchedule
    from apps.machines.models import MakerspaceMachineTypePolicy
    from apps.makerspaces.local_time import local_now
    today = today or local_now(machine.makerspace).date()
    policy = MakerspaceMachineTypePolicy.objects.filter(
        makerspace_id=machine.makerspace_id, machine_type_id=machine.machine_type_id).first()
    grace_days = policy.grace_days if policy else 0
    meters_on = meters_active(machine.makerspace)

    def reading(row):
        value = readings(row)
        return value["hours"], value["jobs"]

    rows = MaintenanceSchedule.objects.filter(machine=machine, is_active=True, blocks_use=True)
    return [row for row in rows
            if schedule_blocks(row, today, grace_days, meters_on=meters_on, reading=lambda row=row: reading(row))]


def require_not_locked_out(machine, *, today=None):
    schedules = blocking_schedules(machine, today=today)
    if schedules:
        raise MachineLockedOut(schedules)

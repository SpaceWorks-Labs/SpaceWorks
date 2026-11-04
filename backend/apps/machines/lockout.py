"""Maintenance lockout (machines D6, MT5): an overdue blocking schedule stops new work.

A schedule marked `blocks_use` that is overdue past the type's grace days (the reminder
policy's `grace_days`, default 0) locks the machine: no job starts on it, and machine
sessions (L23) refuse it the same way. Inert while `machines.maintenance` is off or the
maintenance app is tombstoned. The lock clears itself when the schedule is completed.
"""

from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException

FEATURE = "machines.maintenance"


class MachineLockedOut(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "machine_locked_out"

    def __init__(self, schedules):
        super().__init__({"detail": "Overdue safety maintenance blocks this machine.",
                          "code": "machine_locked_out", "schedule_ids": [row.pk for row in schedules]},
                         "machine_locked_out")


def blocking_schedules(machine, *, today=None):
    from apps.makerspaces.platform import feature_enabled
    from apps.separability.registry import runtime_active
    if not runtime_active("maintenance") or not feature_enabled(machine.makerspace, FEATURE):
        return []
    from apps.maintenance.meters import due
    from apps.maintenance.models import MaintenanceSchedule
    from apps.machines.models import MakerspaceMachineTypePolicy
    today = today or timezone.localdate()
    policy = MakerspaceMachineTypePolicy.objects.filter(
        makerspace_id=machine.makerspace_id, machine_type_id=machine.machine_type_id).first()
    grace = timedelta(days=(policy.grace_days if policy and policy.grace_days else 0))
    rows = MaintenanceSchedule.objects.filter(machine=machine, is_active=True, blocks_use=True)
    return [row for row in rows if due(row, today - grace)]


def require_not_locked_out(machine, *, today=None):
    schedules = blocking_schedules(machine, today=today)
    if schedules:
        raise MachineLockedOut(schedules)

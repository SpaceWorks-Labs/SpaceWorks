"""Allowlisted source facts; never read notes, payloads or free-text identity."""

from django.db.models import DateTimeField
from django.db.models.functions import Coalesce

from apps.machines.models import MachineUsageEntry
from apps.makerspaces.platform import module_enabled
from apps.operations.reports_common import apply_range, period_expression
from .reports_machine_common import machines, requests, space_ids, type_q

TERMINAL = ("completed", "collected", "failed")


def service_facts(space, scope, date_range=None, grain="day", *, intervals=False):
    if not module_enabled(space, "machine_service"):
        return []
    qs = requests(space, scope).filter(status__in=TERMINAL)
    qs = qs.annotate(terminal_at=Coalesce("completed_at", "failed_at")).filter(terminal_at__isnull=False)
    if intervals:
        qs = qs.filter(started_at__isnull=False, terminal_at__isnull=False)
        if date_range:
            start, end = date_range
            if start:
                qs = qs.filter(terminal_at__gt=start)
            if end:
                qs = qs.filter(started_at__lt=end)
    else:
        qs = apply_range(qs, "terminal_at", date_range)
    return qs.annotate(period=period_expression("terminal_at", grain, makerspace=space)).values(
        "id", "makerspace_id", "member_id", "assigned_machine_id", "assigned_machine__name",
        "assigned_machine__machine_type_id", "assigned_machine__machine_type__name",
        "queue__machine_type_id", "queue__machine_type__name", "started_at", "terminal_at",
        "period", "status", "actual_minutes", "estimated_minutes", "fail_percent_complete",
    ).iterator()


def manual_facts(space, scope, date_range=None, grain="day", *, intervals=False):
    qs = MachineUsageEntry.objects.filter(machine__in=machines(space, scope)).order_by()
    if intervals:
        # A creation timestamp is not evidence of when manual work happened.
        qs = qs.filter(started_at__isnull=False)
        if date_range and date_range[1]:
            qs = qs.filter(started_at__lt=date_range[1])
    else:
        # created_at uses a custom DateTimeField subclass; declare their common
        # type so both range lookups and calendar truncation can resolve it.
        qs = qs.annotate(measured_at=Coalesce(
            "started_at", "created_at", output_field=DateTimeField(),
        ))
        qs = apply_range(qs, "measured_at", date_range)
    timestamp = "started_at" if intervals else "measured_at"
    return qs.annotate(period=period_expression(timestamp, grain, makerspace=space)).values(
        "machine__makerspace_id", "machine_id", "machine__name", "machine__machine_type_id", "machine__machine_type__name",
        "member_id", "started_at", "hours", "period",
    ).iterator()


def booking_facts(space, scope, date_range=None, grain="day", *, intervals=False):
    if not module_enabled(space, "bookings"):
        return []
    from apps.bookings.models import Booking
    qs = Booking.objects.filter(
        space__makerspace_id__in=space_ids(space), space__machine_type__isnull=False,
        status__in=("confirmed", "completed", "no_show"),
    ).filter(type_q(scope, "space__machine_type_id")).order_by()
    if intervals:
        if date_range:
            start, end = date_range
            if start:
                qs = qs.filter(ends_at__gt=start)
            if end:
                qs = qs.filter(starts_at__lt=end)
    else:
        qs = apply_range(qs, "starts_at", date_range)
    return qs.annotate(period=period_expression("starts_at", grain, makerspace=space)).values(
        "space__makerspace_id", "space__machine_type_id", "space__machine_type__name", "member_id", "starts_at", "ends_at", "period",
    ).iterator()

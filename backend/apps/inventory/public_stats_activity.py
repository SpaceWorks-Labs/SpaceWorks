"""Period figures for the machines, printing and lending sections (#170).

The existing section payloads (all-time machine hours, the printer kernel figures, the
lending library) are unchanged; these add what happened in the space's fixed period, read
from the same canonical rows with the same public filters. Counts pass suppression.
"""

from django.db.models import Sum

from .public_stats_period import in_window, suppressed


def machine_hours(makerspace, window):
    from apps.machines.models import MachineUsageEntry
    rows = MachineUsageEntry.objects.filter(machine__makerspace=makerspace, machine__is_public=True,
                                            machine__is_active=True)
    total = in_window(rows, "created_at", window).aggregate(total=Sum("hours"))["total"]
    return round(float(total or 0), 2)


def printing_figures(makerspace, window):
    """Hours and completed jobs in the period, from the kernel `public_printer_stats` reads."""
    from apps.machines.models import MachineServiceRequest, MachineUsageEntry
    from apps.machines.printer_capabilities import resolve_global_printer_type
    from apps.machines.public_printer_stats import COMPLETED

    printer_type = resolve_global_printer_type()
    if printer_type is None:
        return {"hours": 0.0, "jobs": suppressed(0)}
    done = in_window(MachineServiceRequest.objects.filter(
        makerspace=makerspace, queue__machine_type=printer_type, status__in=COMPLETED), "completed_at", window)
    manual = in_window(MachineUsageEntry.objects.filter(
        machine__makerspace=makerspace, machine__machine_type=printer_type,
        source=MachineUsageEntry.Source.TYPED_MANUAL), "created_at", window)
    minutes = done.aggregate(total=Sum("actual_minutes"))["total"] or 0
    hours = float(manual.aggregate(total=Sum("hours"))["total"] or 0)
    return {"hours": round(minutes / 60 + hours, 2), "jobs": suppressed(done.count())}


def lending_loans(makerspace, window):
    """Loans that went out in the period and include at least one publicly listed tool."""
    from apps.hardware_requests.models import HardwareRequest

    from .models import PublicAvailabilityMode
    rows = HardwareRequest.objects.filter(
        makerspace=makerspace, issued_at__isnull=False, items__issued_quantity__gt=0,
        items__product__is_public=True, items__product__is_archived=False,
    ).exclude(items__product__public_availability_mode=PublicAvailabilityMode.HIDDEN)
    return suppressed(in_window(rows, "issued_at", window).values("pk").distinct().count())

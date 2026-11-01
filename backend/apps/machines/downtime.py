"""The downtime ledger writer (machines D7, MT6), driven by machine status changes.

`status_tracking.change_status` calls `track` under the machine lock: going to
maintenance or offline opens a period (one open period per machine, DB-enforced), coming
back to idle or running closes it. Behind `machines.maintenance`; with it off nothing is
recorded, exactly release 1's behaviour.
"""

from django.utils import timezone

DOWN = ("maintenance", "offline")
FEATURE = "machines.maintenance"


def _on(machine):
    from apps.makerspaces.platform import feature_enabled
    return feature_enabled(machine.makerspace, FEATURE)


def track(machine, previous, status, *, actor=None, reason="", expected_back_at=None):
    from apps.audit.services import record

    from .models import MachineDowntime
    if previous == status or not _on(machine):
        return None
    open_row = MachineDowntime.objects.select_for_update().filter(machine=machine, ended_at__isnull=True).first()
    if open_row is not None and (status not in DOWN or open_row.kind != status):
        open_row.ended_at, open_row.ended_by = timezone.now(), actor
        open_row.save(update_fields=["ended_at", "ended_by"])
        record(actor, "machine.downtime_ended", makerspace=machine.makerspace, target=machine,
               meta={"downtime_id": open_row.pk, "kind": open_row.kind})
        open_row = None
    if status in DOWN and open_row is None:
        row = MachineDowntime.objects.create(
            makerspace_id=machine.makerspace_id, machine=machine, kind=status, reason=str(reason or "")[:300],
            expected_back_at=expected_back_at, started_by=actor)
        record(actor, "machine.downtime_started", makerspace=machine.makerspace, target=machine,
               meta={"downtime_id": row.pk, "kind": status})
        return row
    return open_row


def update_open(machine, actor, *, reason=None, expected_back_at=None):
    """Staff learn more while a machine is down: reason and expected-back stay editable."""
    from apps.audit.services import record

    from .models import MachineDowntime
    row = MachineDowntime.objects.select_for_update().filter(machine=machine, ended_at__isnull=True).first()
    if row is None:
        return None
    if reason is not None:
        row.reason = str(reason)[:300]
    if expected_back_at is not None:
        row.expected_back_at = expected_back_at
    row.save(update_fields=["reason", "expected_back_at"])
    record(actor, "machine.downtime_updated", makerspace=machine.makerspace, target=machine,
           meta={"downtime_id": row.pk})
    return row


def summary(machine, *, days=30, now=None):
    """Uptime share and mean time to repair over the last `days` (closed and open periods)."""
    from datetime import timedelta

    from .models import MachineDowntime
    now = now or timezone.now()
    since = now - timedelta(days=days)
    rows = list(MachineDowntime.objects.filter(machine=machine).exclude(ended_at__lt=since))
    down = sum(((row.ended_at or now) - max(row.started_at, since)).total_seconds() for row in rows)
    closed = [row for row in rows if row.ended_at]
    repair = (sum((row.ended_at - row.started_at).total_seconds() for row in closed) / len(closed)) if closed else None
    window = days * 86400
    return {"days": days, "uptime_percent": round(100 * max(window - down, 0) / window, 1),
            "periods": len(rows), "mean_hours_to_repair": round(repair / 3600, 1) if repair is not None else None}

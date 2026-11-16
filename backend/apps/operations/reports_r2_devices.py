"""Release-0.12 device-adapter and machine-access reports: counts only, no person is named."""

from datetime import timedelta

from django.db.models import Count, Sum
from django.utils import timezone

from apps.operations.reports_r2_common import metric_report


def _may(actor, action, space):
    """`actor=None` is the trusted internal seam; otherwise the actor must hold ``action`` in this space."""
    from apps.accounts import rbac
    return actor is None or rbac.can(actor, action, space.pk)


def _visible_bindings(actor, space):
    """The binding ids a machine-scoped actor may count, or ``None`` for every row (decision 336i, 338).

    The same rule as the adapter console: a non-machine target, or a machine inside the actor's scope; a
    Space Manager or superadmin is unrestricted. Rows whose binding is gone name no machine, so only an
    unrestricted actor counts them.
    """
    if actor is None:
        return None
    from apps.devices.adapter_access import _unrestricted
    from apps.devices.models import AdapterBinding
    from apps.machines.access import can_manage_machine
    if _unrestricted(actor, space.pk):
        return None
    rows = AdapterBinding.objects.filter(makerspace=space).select_related("machine")
    return {row.pk for row in rows if row.machine is None or can_manage_machine(actor, row.machine)}


def _adapter_rows(space, start, end, *, actor=None):
    if not _may(actor, _manage_devices(), space):
        return []
    from apps.devices.models import (
        AdapterAccessLog, AdapterArtifact, AdapterCommand, AdapterEvent, AdapterTelemetryDrop, AdapterTelemetryPoint,
        AdapterUsageLog, Device,
    )
    visible = _visible_bindings(actor, space)
    adapters = Device.objects.filter(makerspace=space, kind=Device.Kind.ADAPTER)
    usage = AdapterUsageLog.objects.filter(makerspace=space, started_at__gte=start, started_at__lt=end)
    access = AdapterAccessLog.objects.filter(makerspace=space, created_at__gte=start, created_at__lt=end)
    commands = AdapterCommand.objects.filter(makerspace=space, created_at__gte=start, created_at__lt=end)
    events = AdapterEvent.objects.filter(makerspace=space, received_at__gte=start, received_at__lt=end)
    artifacts = AdapterArtifact.objects.filter(makerspace=space, captured_at__gte=start, captured_at__lt=end)
    points = AdapterTelemetryPoint.objects.filter(makerspace=space, resolution=0, ts__gte=start, ts__lt=end)
    if visible is not None:
        adapters = adapters.filter(adapter_bindings__pk__in=visible).distinct()
        usage, access = usage.filter(binding_id__in=visible), access.filter(binding_id__in=visible)
        commands, events = commands.filter(binding_id__in=visible), events.filter(binding_id__in=visible)
        artifacts, points = artifacts.filter(binding_id__in=visible), points.filter(binding_id__in=visible)
    # `end` is exclusive and defaults to "now", so the last day counted is the one holding its final instant:
    # `day__lt=end.date()` silently left out today's drops in the default window.
    last_day = (end - timedelta(microseconds=1)).date()
    dropped = AdapterTelemetryDrop.objects.filter(
        makerspace=space, day__gte=start.date(), day__lte=last_day).aggregate(n=Sum("count"))["n"] or 0
    sums = usage.aggregate(active=Sum("active_minutes"), idle=Sum("idle_minutes"))
    rows = [
        ("adapters_active", adapters.filter(status=Device.Status.ACTIVE).count()),
        ("usage_sessions", usage.count()),
        ("usage_failed_sessions", usage.exclude(error_code="").count()),
        ("usage_active_minutes", sums["active"] or 0),
        ("usage_idle_minutes", sums["idle"] or 0),
        ("access_allowed", access.filter(allowed=True).count()),
        ("access_denied", access.filter(allowed=False).count()),
        ("access_decided_offline", access.filter(offline=True).count()),
        ("commands_sent", commands.count()),
        ("commands_succeeded", commands.filter(status="succeeded").count()),
        ("commands_failed", commands.filter(status__in=("failed", "expired")).count()),
        ("telemetry_samples", points.count()),
        ("media_captured", artifacts.count()),
    ]
    if visible is None:
        # The drop counter is per space, not per machine: a machine-scoped actor must not read it.
        rows.insert(-1, ("telemetry_samples_dropped", dropped))
    # Detections and jobs arrive as typed events; one row per type keeps new adapter kinds visible.
    rows += [(f"event:{row['event_type']}", row["n"]) for row in
             events.order_by().values("event_type").annotate(n=Count("pk")).order_by("event_type")]
    return rows


def build_device_adapter_activity(makerspace_id, *, limit=None, date_range=None, actor=None, grain=None):
    if actor is not None:
        _require_devices_actor(actor, makerspace_id)

    def rows(space, start, end):
        return _adapter_rows(space, start, end, actor=actor)
    return metric_report(makerspace_id, ("devices",), rows, limit=limit, date_range=date_range,
                         definition="Adapter usage, access decisions, commands, telemetry, media and typed events.")


def _manage_devices():
    from apps.accounts import rbac
    return rbac.Action.MANAGE_DEVICES


def _require_devices_actor(actor, makerspace_id):
    from rest_framework.exceptions import PermissionDenied

    from apps.admin_api.permissions import active_user
    if not active_user(actor):
        raise PermissionDenied()
    from apps.accounts import rbac
    if makerspace_id is not None and not rbac.can(actor, _manage_devices(), makerspace_id):
        raise PermissionDenied()


def _grant_rows(space, start, end, *, actor=None):
    from apps.machines.access_grants_services import manageable_grants
    from apps.machines.models import MachineAccessGrant
    now = timezone.now()
    grants = MachineAccessGrant.objects.filter(makerspace=space)
    if actor is not None:
        # A Machine Manager counts only the grants they could manage (the staff list's authority);
        # `actor=None` is the trusted internal / organization roll-up seam, as for every machine report.
        reach = manageable_grants(actor, grants.select_related("makerspace", "machine", "machine_type"))
        grants = grants.filter(pk__in=[row.pk for row in reach])
    live = grants.filter(revoked_at__isnull=True).exclude(expires_at__lt=now)
    return [
        ("live_grants", live.count()),
        ("live_machine_grants", live.filter(machine__isnull=False).count()),
        ("live_machine_type_grants", live.filter(machine_type__isnull=False).count()),
        ("granted_in_period", grants.filter(granted_at__gte=start, granted_at__lt=end).count()),
        ("revoked_in_period", grants.filter(revoked_at__gte=start, revoked_at__lt=end).count()),
        ("expired_unrevoked", grants.filter(revoked_at__isnull=True, expires_at__lt=now).count()),
        ("expiring_within_30_days", live.filter(expires_at__isnull=False,
                                                expires_at__lt=now + timedelta(days=30)).count()),
        ("converted_from_certification", grants.filter(source="migration").count()),
    ]


def build_machine_access_grants(makerspace_id, *, limit=None, date_range=None, actor=None, grain=None):
    if actor is not None:
        from rest_framework.exceptions import PermissionDenied

        from apps.accounts import rbac
        from apps.admin_api.permissions import active_user
        if not active_user(actor):
            raise PermissionDenied()
        if makerspace_id is not None and not rbac.can(actor, rbac.Action.MANAGE_MACHINES, makerspace_id):
            raise PermissionDenied()

    def rows(space, start, end):
        return _grant_rows(space, start, end, actor=actor)
    return metric_report(makerspace_id, ("machines",), rows, limit=limit, date_range=date_range,
                         definition="Machine access grants in counts: nothing here names a member.")

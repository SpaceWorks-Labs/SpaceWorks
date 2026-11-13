"""telemetry.history: time series of temperatures, metrics and sensor readings, thinned out over time.

Raw samples (resolution 0) are kept ``ADAPTER_TELEMETRY_RAW_HOURS`` (24 h), then rolled into one-minute buckets kept
``..._MINUTE_DAYS`` (7 d), then into fifteen-minute buckets kept ``..._QUARTER_DAYS`` (90 d), then deleted. A rollup
carries avg/min/max/n so a chart can draw a band. Recording is fail-safe: a problem here never fails a status report.
"""
from django.utils.translation import gettext
import logging
from datetime import datetime, timedelta, timezone as dt_timezone

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.devices.adapter_access import HISTORY_SWITCH, adapters_enabled, scoped_binding
from apps.devices.models import AdapterTelemetryPoint

logger = logging.getLogger(__name__)
RAW, MINUTE, QUARTER = 0, 60, 900
BATCH = 5000
MAX_POINTS = 2000
MAX_SERIES_PER_REPORT = 40


def _cfg(name, default):
    return int(getattr(settings, name, default))


def windows():
    return {"raw": timedelta(hours=_cfg("ADAPTER_TELEMETRY_RAW_HOURS", 24)),
            "minute": timedelta(days=_cfg("ADAPTER_TELEMETRY_MINUTE_DAYS", 7)),
            "quarter": timedelta(days=_cfg("ADAPTER_TELEMETRY_QUARTER_DAYS", 90))}


def _numbers(prefix, block):
    if not isinstance(block, dict):
        return {}
    return {f"{prefix}.{key}"[:80]: float(value) for key, value in block.items()
            if isinstance(value, (int, float)) and not isinstance(value, bool)}


def record_status(binding, payload, observed):
    """Store the numeric telemetry of one status item when the history switch and capability are on."""
    try:
        if "telemetry.history" not in binding.capabilities or not adapters_enabled(binding.makerspace_id, HISTORY_SWITCH):
            return
        block = payload.get("telemetry") or {}
        series = {**_numbers("temp", block.get("temperatures")), **_numbers("metric", block.get("metrics"))}
        _store(binding, series, observed)
    except Exception:  # noqa: BLE001 - history must never fail a status report
        logger.warning("adapter telemetry history failed", exc_info=True)


def record_sensor(binding, data, observed):
    try:
        if binding is None or "telemetry.history" not in binding.capabilities \
                or not adapters_enabled(binding.makerspace_id, HISTORY_SWITCH):
            return
        _store(binding, {f"sensor.{data['sensor']}"[:80]: float(data["value"])}, observed)
    except Exception:  # noqa: BLE001
        logger.warning("adapter sensor history failed", exc_info=True)


def _store(binding, series, observed):
    rows = [AdapterTelemetryPoint(makerspace_id=binding.makerspace_id, binding=binding, series=name, resolution=RAW,
                                  ts=observed, avg=value, min=value, max=value, n=1)
            for name, value in list(series.items())[:MAX_SERIES_PER_REPORT]]
    if rows:
        from apps.managed_hosting.extra_quotas import extra_quota_allows
        # Decision 328a: at the limit new samples are not stored (a status report cannot carry a 409); stored ones stay.
        if not extra_quota_allows(binding.makerspace, "adapter_telemetry_points", adding=len(rows)):
            from apps.devices.telemetry_drops import record_drop
            record_drop(binding.makerspace_id, len(rows))  # visible loss: console, 100% notice, activity report
            return
        AdapterTelemetryPoint.objects.bulk_create(rows, ignore_conflicts=True)


def _bucket(ts, seconds):
    epoch = int(ts.timestamp())
    return datetime.fromtimestamp(epoch - epoch % seconds, tz=dt_timezone.utc)


def _roll(source, target, cutoff, space_id=None):
    """Fold up to BATCH source rows older than ``cutoff`` into ``target`` buckets (merging), then delete them."""
    scope = AdapterTelemetryPoint.objects.filter(makerspace_id=space_id) if space_id else AdapterTelemetryPoint.objects
    rows = list(scope.filter(resolution=source, ts__lt=cutoff).order_by("ts")[:BATCH])
    groups = {}
    for row in rows:
        key = (row.binding_id, row.makerspace_id, row.series, _bucket(row.ts, target))
        sums = groups.setdefault(key, [0.0, row.min, row.max, 0])
        sums[0] += row.avg * row.n
        sums[1], sums[2], sums[3] = min(sums[1], row.min), max(sums[2], row.max), sums[3] + row.n
    with transaction.atomic():
        for (binding_id, space_id, series, ts), (total, low, high, n) in groups.items():
            current = AdapterTelemetryPoint.objects.select_for_update().filter(
                binding_id=binding_id, series=series, resolution=target, ts=ts).first()
            if current is None:
                AdapterTelemetryPoint.objects.create(makerspace_id=space_id, binding_id=binding_id, series=series,
                                                     resolution=target, ts=ts, avg=total / n, min=low, max=high, n=n)
            else:
                merged = current.n + n
                current.avg = (current.avg * current.n + total) / merged
                current.min, current.max, current.n = min(current.min, low), max(current.max, high), merged
                current.save(update_fields=["avg", "min", "max", "n"])
        AdapterTelemetryPoint.objects.filter(pk__in=[row.pk for row in rows]).delete()
    return len(rows)


def due_points(now):
    """Every telemetry row the next sweep would fold or expire (the retention driver reads its spaces from this)."""
    from django.db.models import Q
    win = windows()
    return AdapterTelemetryPoint.objects.filter(Q(resolution=RAW, ts__lt=now - win["raw"])
                                                | Q(resolution=MINUTE, ts__lt=now - win["minute"])
                                                | Q(resolution=QUARTER, ts__lt=now - win["quarter"]))


def sweep(now=None, space_id=None):
    """Downsample and expire (idempotent; called by the Celery task). Returns the rows folded or deleted."""
    now, win = now or timezone.now(), windows()
    folded = _roll(RAW, MINUTE, now - win["raw"], space_id) + _roll(MINUTE, QUARTER, now - win["minute"], space_id)
    scope = AdapterTelemetryPoint.objects.filter(makerspace_id=space_id) if space_id else AdapterTelemetryPoint.objects
    expired, _ = scope.filter(resolution=QUARTER, ts__lt=now - win["quarter"]).delete()
    return folded + expired


def _resolution(since, now, win):
    if since >= now - win["raw"]:
        return RAW
    return MINUTE if since >= now - win["minute"] else QUARTER


def read(actor, binding_id, params):
    """Chart data for staff in scope. Auto-picks the finest resolution that still covers ``since``."""
    binding = scoped_binding(actor, binding_id, child=HISTORY_SWITCH)
    now, win = timezone.now(), windows()
    since = _when(params.get("since"), "since") or now - timedelta(hours=6)
    until = _when(params.get("until"), "until") or now
    series = params.get("series", "")[:80]
    resolution = int(params["resolution"]) if str(params.get("resolution", "")).isdigit() \
        and int(params["resolution"]) in (RAW, MINUTE, QUARTER) else _resolution(since, now, win)
    base = AdapterTelemetryPoint.objects.filter(binding=binding)
    names = sorted(base.filter(ts__gte=now - win["quarter"]).values_list("series", flat=True).distinct()[:100])
    points = []
    if series:
        points = [{"ts": row.ts, "avg": row.avg, "min": row.min, "max": row.max, "n": row.n}
                  for row in base.filter(series=series, resolution=resolution, ts__gte=since, ts__lte=until
                                         ).order_by("ts")[:MAX_POINTS]]
    return {"binding_id": str(binding.pk), "series": names, "selected": series, "resolution": resolution,
            "points": points}


def _when(raw, name):
    if not raw:
        return None
    from django.utils.dateparse import parse_datetime
    value = parse_datetime(raw)
    if value is None:
        raise ValidationError({name: gettext("Use an ISO 8601 date-time.")})
    return value

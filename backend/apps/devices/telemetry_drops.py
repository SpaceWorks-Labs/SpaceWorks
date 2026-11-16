"""Per-day count of telemetry samples dropped at the `adapter_telemetry_points` limit (decision 328a).

One row per space per day, bumped with an F() update (no per-sample rows). Never raises: counting a drop must not
break a status report.
"""
import logging
from datetime import timedelta

from django.db.models import F, Sum
from django.utils import timezone

logger = logging.getLogger(__name__)


def record_drop(makerspace_id, count):
    from apps.devices.models import AdapterTelemetryDrop

    try:
        day = timezone.now().date()
        AdapterTelemetryDrop.objects.get_or_create(makerspace_id=makerspace_id, day=day)
        AdapterTelemetryDrop.objects.filter(makerspace_id=makerspace_id, day=day).update(count=F("count") + int(count))
    except Exception:  # noqa: BLE001
        logger.warning("adapter_telemetry_drop_uncounted", extra={"makerspace_id": makerspace_id})


def dropped_since(makerspace_id, days):
    """Samples dropped in the last ``days`` days (today included)."""
    from apps.devices.models import AdapterTelemetryDrop

    first = timezone.now().date() - timedelta(days=days - 1)
    return int(AdapterTelemetryDrop.objects.filter(makerspace_id=makerspace_id, day__gte=first)
               .aggregate(n=Sum("count"))["n"] or 0)

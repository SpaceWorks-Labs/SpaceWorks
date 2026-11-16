"""Store a printer's bounded status snapshot from its signed heartbeat (release 2 L10).

Idempotent: the snapshot carries ``observed_at``; one that is not newer than the stored
row changes nothing (``stale``), so a retried or reordered heartbeat is harmless. It is
also rate-limited per device: a snapshot arriving within ``MIN_INTERVAL_SECONDS`` of the
last stored one is dropped (``throttled``). The heartbeat itself always succeeds; a
device without the integration is told ``not_integrated`` and nothing is written.
"""
from django.utils.translation import gettext
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from apps.devices.integration_access import device_binding
from apps.devices.models import Device, PrinterStatusSnapshot
from apps.devices.services_locks import lock_tenant

MIN_INTERVAL_SECONDS = 5
MAX_FUTURE_SECONDS = 300


def _temperature(temperatures, key):
    value = (temperatures or {}).get(key)
    return None if value is None else Decimal(str(value))


def store_snapshot(principal, payload, *, now=None):
    now = now or timezone.now()
    observed = datetime.fromtimestamp(payload["observed_at"], tz=dt_timezone.utc)
    if observed > now + timedelta(seconds=MAX_FUTURE_SECONDS):
        raise ValidationError({"status_snapshot": {"observed_at": gettext("The observation time is in the future.")}})
    with transaction.atomic():
        makerspace = lock_tenant(principal.makerspace_id)
        device = Device.objects.select_for_update().get(pk=principal.device_id, makerspace=makerspace)
        try:
            device_binding(device)
        except NotFound:
            return "not_integrated"
        current = PrinterStatusSnapshot.objects.select_for_update().filter(device=device).first()
        if current is not None and observed <= current.observed_at:
            return "stale"
        if current is not None and now - current.received_at < timedelta(seconds=MIN_INTERVAL_SECONDS):
            return "throttled"
        temperatures = payload.get("temperatures")
        PrinterStatusSnapshot.objects.update_or_create(device=device, defaults={
            "makerspace": makerspace, "schema_version": payload["schema_version"], "state": payload["state"],
            "progress_percent": payload["progress_percent"], "layer_current": payload["layer_current"],
            "layer_total": payload["layer_total"], "nozzle_temp_c": _temperature(temperatures, "nozzle"),
            "bed_temp_c": _temperature(temperatures, "bed"), "chamber_temp_c": _temperature(temperatures, "chamber"),
            "spools": [dict(row) for row in payload.get("spools", [])], "clear_token": payload["clear_token"],
            "observed_at": observed, "received_at": now,
        })
    return "stored"

"""Atomic settings update, separate from Metabase provisioning and its credentials."""
from django.db import transaction
from contextlib import nullcontext

from apps.audit.services import record
from .models import AnalyticsConnection, PlatformAnalyticsConnection
from apps.makerspaces.telemetry_defaults import defaults
from .telemetry_serializers import TelemetryConfigSerializer


def _query(scope):
    if scope.platform:
        return PlatformAnalyticsConnection.objects.filter(singleton=True)
    return AnalyticsConnection.objects.filter(makerspace=scope.makerspace)


def describe(scope):
    row = _query(scope).first()
    data = row.telemetry_config if row else {}
    serializer = TelemetryConfigSerializer(data=data or defaults())
    return serializer.validated_data if serializer.is_valid() else defaults()


def update(scope, actor, config):
    from apps.tenant_migration.gate_runtime import tenant_write

    gate = nullcontext() if scope.platform else tenant_write(scope.makerspace.pk)
    with gate, transaction.atomic():
        if scope.platform:
            row, _ = PlatformAnalyticsConnection.objects.get_or_create(singleton=True)
        else:
            row, _ = AnalyticsConnection.objects.get_or_create(makerspace=scope.makerspace)
        row = _query(scope).select_for_update().get(pk=row.pk)
        if row.telemetry_config != config:
            old = row.telemetry_config if isinstance(row.telemetry_config, dict) else {}
            changed = sorted(key for key in config if old.get(key) != config[key])
            row.telemetry_config = config
            row.save(update_fields=["telemetry_config", "updated_at"])
            record(actor, "analytics.telemetry_updated", makerspace=scope.makerspace, target=row,
                   meta={"scope": scope.label, "fields": changed,
                         "pageview_enabled": config["pageview"]["provider"] != "none",
                         "replay_enabled": config["replay"]["provider"] != "none",
                         "sentry_enabled": config["diagnostics"]["sentry"]["enabled"],
                         "firebase_performance_enabled": config["diagnostics"]["firebase_performance"]["enabled"]})
    return config

"""Public projection for an already resolved tenant, safe when analytics is absent."""
from django.apps import apps

from .platform import module_enabled
from .telemetry_defaults import defaults
from .telemetry_schema import TelemetryConfigSerializer


def effective_telemetry(makerspace):
    if not apps.is_installed("apps.analytics") or not module_enabled(makerspace, "analytics"):
        return defaults()
    model = apps.get_model("analytics", "AnalyticsConnection")
    row = model.objects.filter(makerspace=makerspace).only("telemetry_config").first()
    serializer = TelemetryConfigSerializer(data=(row.telemetry_config if row else {}) or defaults())
    return serializer.validated_data if serializer.is_valid() else defaults()


def platform_telemetry():
    if not apps.is_installed("apps.analytics"):
        return defaults()
    model = apps.get_model("analytics", "PlatformAnalyticsConnection")
    row = model.objects.filter(singleton=True).only("telemetry_config").first()
    serializer = TelemetryConfigSerializer(data=(row.telemetry_config if row else {}) or defaults())
    return serializer.validated_data if serializer.is_valid() else defaults()


def legacy_allowed(makerspace=None):
    """Only genuinely unconfigured installations may retain the legacy tracker."""
    if not apps.is_installed("apps.analytics"):
        return False
    if makerspace is not None:
        if not module_enabled(makerspace, "analytics"):
            return False
        model = apps.get_model("analytics", "AnalyticsConnection")
        row = model.objects.filter(makerspace=makerspace).only("telemetry_config").first()
    else:
        model = apps.get_model("analytics", "PlatformAnalyticsConnection")
        row = model.objects.filter(singleton=True).only("telemetry_config").first()
    return row is None or row.telemetry_config == {}

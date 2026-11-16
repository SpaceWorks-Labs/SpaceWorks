"""/control/ "Integrations & analytics": Metabase / Grafana connections, read-only (0.12.0).

Connections are set up, tested and rotated in the web console (Platform analytics, a space's
Analytics settings) through ``apps.analytics`` services, which encrypt and audit them. Keys,
tokens and the database login show here only as set or not set; the telemetry settings are left
out because they may carry provider secrets.
"""

from django.contrib import admin

from apps.analytics.models import AnalyticsConnection, PlatformAnalyticsConnection
from config.admin_records import ControlRecordAdmin

_HIDDEN = ("telemetry_config",)


@admin.register(AnalyticsConnection)
class AnalyticsConnectionAdmin(ControlRecordAdmin):
    list_display = ("makerspace", "provider", "metabase_url", "grafana_url", "secret__embed_secret",
                    "secret__grafana_token", "show_member_details", "updated_at")
    list_filter = ("provider", "show_member_details")
    search_fields = ("makerspace__name", "metabase_url", "grafana_url")
    list_select_related = ("makerspace",)
    ordering = ("makerspace__name",)
    hidden_fields = _HIDDEN


@admin.register(PlatformAnalyticsConnection)
class PlatformAnalyticsConnectionAdmin(ControlRecordAdmin):
    makerspace_lookup = None
    list_display = ("provider", "metabase_url", "grafana_url", "secret__embed_secret", "secret__grafana_token",
                    "updated_at")
    hidden_fields = _HIDDEN

"""Mounted at ``api/v1/admin/``. Route classes live in accounts/delegated_route_catalog_r2.py:
the viewer routes are delegable (``view_analytics`` may come from an organization grant), the
manager routes membership-only and the platform routes platform-only."""

from django.urls import path
from . import grafana_api
from .telemetry_api import TelemetryView

from .api import (
    AnalyticsConnectionView, AnalyticsEmbedView, AnalyticsLoginRotateView, AnalyticsLoginView,
    AnalyticsSummaryView, platform,
)

SPACE = "makerspaces/<int:makerspace_id>/metabase"
PLATFORM = "platform/metabase"

urlpatterns = [
    path("makerspaces/<int:makerspace_id>/telemetry", TelemetryView.as_view(), name="admin-makerspace-telemetry"),
    path("platform/telemetry", platform(TelemetryView).as_view(), name="admin-platform-telemetry"),
    path(SPACE, AnalyticsSummaryView.as_view(), name="admin-makerspace-analytics"),
    path(f"{SPACE}/connection", AnalyticsConnectionView.as_view(), name="admin-makerspace-analytics-connection"),
    path(f"{SPACE}/login", AnalyticsLoginView.as_view(), name="admin-makerspace-analytics-login"),
    path(f"{SPACE}/login/rotate", AnalyticsLoginRotateView.as_view(), name="admin-makerspace-analytics-login-rotate"),
    path(f"{SPACE}/dashboards/<int:dashboard_id>/embed", AnalyticsEmbedView.as_view(),
         name="admin-makerspace-analytics-embed"),
    path(PLATFORM, platform(AnalyticsSummaryView).as_view(), name="admin-platform-analytics"),
    path(f"{PLATFORM}/connection", platform(AnalyticsConnectionView).as_view(),
         name="admin-platform-analytics-connection"),
    path(f"{PLATFORM}/login", platform(AnalyticsLoginView).as_view(), name="admin-platform-analytics-login"),
    path(f"{PLATFORM}/login/rotate", platform(AnalyticsLoginRotateView).as_view(),
         name="admin-platform-analytics-login-rotate"),
    path(f"{PLATFORM}/dashboards/<int:dashboard_id>/embed", platform(AnalyticsEmbedView).as_view(),
         name="admin-platform-analytics-embed"),
]

# Decision 263: Grafana, the same handlers at both scopes (admin-{makerspace,platform}-grafana*).
_GRAFANA = (
    ("", grafana_api.GrafanaSummaryView, ""),
    ("/connection", grafana_api.GrafanaConnectionView, "-connection"),
    ("/token", grafana_api.GrafanaTokenView, "-token"),
    ("/test", grafana_api.GrafanaTestView, "-test"),
    ("/bundle", grafana_api.GrafanaBundleView, "-bundle"),
    ("/dashboards/<slug:uid>/embed", grafana_api.GrafanaEmbedView, "-embed"),
    ("/dashboards/<slug:uid>/render", grafana_api.GrafanaRenderView, "-render"),
)
urlpatterns += [
    path(f"makerspaces/<int:makerspace_id>/grafana{suffix}", view.as_view(), name=f"admin-makerspace-grafana{name}")
    for suffix, view, name in _GRAFANA
] + [
    path(f"platform/grafana{suffix}", grafana_api.platform(view).as_view(), name=f"admin-platform-grafana{name}")
    for suffix, view, name in _GRAFANA
]

"""Mounted at ``api/v1/admin/``. Route classes live in accounts/delegated_route_catalog_r2.py:
the viewer routes are delegable (``view_analytics`` may come from an organization grant), the
manager routes membership-only and the platform routes platform-only."""

from django.urls import path

from .api import (
    AnalyticsConnectionView, AnalyticsEmbedView, AnalyticsLoginRotateView, AnalyticsLoginView,
    AnalyticsSummaryView, platform,
)

SPACE = "makerspaces/<int:makerspace_id>/analytics"
PLATFORM = "platform/analytics"

urlpatterns = [
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

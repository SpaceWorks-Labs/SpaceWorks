"""Staff routes for the public event surface (release 2 L1)."""

from django.urls import path

from .views_event_surface_settings import EventEmbedPolicyView, EventHostOptionsView, EventReportSwitchesView
from .views_short_links_admin import EventShortLinkRegenerateView, EventShortLinkView

urlpatterns = [
    path("events/<int:pk>/short-link/", EventShortLinkView.as_view(), name="admin-event-short-link"),
    path("events/<int:pk>/short-link/regenerate/", EventShortLinkRegenerateView.as_view(),
         name="admin-event-short-link-regenerate"),
    path("events/host-options/", EventHostOptionsView.as_view(), name="admin-event-host-options"),
    path("makerspaces/<int:makerspace_id>/events/embed-policy/", EventEmbedPolicyView.as_view(),
         name="admin-event-embed-policy"),
    path("makerspaces/<int:makerspace_id>/events/report-switches/", EventReportSwitchesView.as_view(),
         name="admin-event-report-switches"),
]

"""Inert F route manifest; G mounts these after installing registry policies."""

from django.urls import path

from .broadcast_views import BroadcastDetailView, BroadcastPreviewView, BroadcastScheduleView, BroadcastTestView
from .broadcast_views_extra import BroadcastSendView, BroadcastTalliesView, BroadcastTemplateListView
from .analytics_views import EventAnalyticsExtrasView

urlpatterns = [
    path("events/<int:pk>/broadcasts/<int:campaign_id>/", BroadcastDetailView.as_view(),
         name="events-programme-admin-broadcasts-detail"),
    path("events/<int:pk>/broadcasts/<int:campaign_id>/preview/", BroadcastPreviewView.as_view(),
         name="events-programme-admin-broadcasts-preview"),
    path("events/<int:pk>/broadcasts/<int:campaign_id>/test/", BroadcastTestView.as_view(),
         name="events-programme-admin-broadcasts-test"),
    path("events/<int:pk>/broadcasts/<int:campaign_id>/schedule/", BroadcastScheduleView.as_view(),
         name="events-programme-admin-broadcasts-schedule"),
    path("events/<int:pk>/broadcasts/<int:campaign_id>/send/", BroadcastSendView.as_view(),
         name="events-programme-admin-broadcasts-send"),
    path("events/<int:pk>/broadcasts/<int:campaign_id>/tallies/", BroadcastTalliesView.as_view(),
         name="events-programme-admin-broadcasts-tallies"),
    path("events/<int:pk>/broadcast-templates/", BroadcastTemplateListView.as_view(),
         name="events-programme-admin-broadcast-templates"),
    path("events/<int:pk>/analytics/extras/", EventAnalyticsExtrasView.as_view(),
         name="events-programme-admin-analytics-extras"),
]

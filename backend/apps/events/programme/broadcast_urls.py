"""Inert F route manifest; G mounts these after installing registry policies."""

from django.urls import path

from .broadcast_views import BroadcastDetailView, BroadcastPreviewView, BroadcastScheduleView, BroadcastTestView

urlpatterns = [
    path("events/<int:pk>/broadcasts/<int:campaign_id>/", BroadcastDetailView.as_view(),
         name="events-programme-admin-broadcasts-detail"),
    path("events/<int:pk>/broadcasts/<int:campaign_id>/preview/", BroadcastPreviewView.as_view(),
         name="events-programme-admin-broadcasts-preview"),
    path("events/<int:pk>/broadcasts/<int:campaign_id>/test/", BroadcastTestView.as_view(),
         name="events-programme-admin-broadcasts-test"),
    path("events/<int:pk>/broadcasts/<int:campaign_id>/schedule/", BroadcastScheduleView.as_view(),
         name="events-programme-admin-broadcasts-schedule"),
]

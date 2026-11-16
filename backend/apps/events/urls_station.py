from django.urls import path

from apps.events.views_checkin_station import (
    EventStationRosterView,
    EventStationSessionView,
    EventStationSyncView,
)
from apps.events.views_station_badges import EventStationBadgeReceiptsView, EventStationBadgeView


urlpatterns = [
    path(
        "event-checkin-stations/<uuid:public_token>/session/",
        EventStationSessionView.as_view(),
        name="event-check-in-station-session",
    ),
    path(
        "event-checkin-stations/<uuid:public_token>/roster/",
        EventStationRosterView.as_view(),
        name="event-check-in-station-roster",
    ),
    path(
        "event-checkin-stations/<uuid:public_token>/sync/",
        EventStationSyncView.as_view(),
        name="event-check-in-station-sync",
    ),
    path(
        "event-checkin-stations/<uuid:public_token>/badge/<int:registration_id>/",
        EventStationBadgeView.as_view(),
        name="event-check-in-station-badge",
    ),
    path(
        "event-checkin-stations/<uuid:public_token>/badge-receipts/",
        EventStationBadgeReceiptsView.as_view(),
        name="event-check-in-station-badge-receipts",
    ),
]

"""Event-series staff routes, split out of `urls_admin.py` for the 300-line ceiling.

Spliced back into `urls_admin.urlpatterns` at their original position, so every path,
route name and resolution order is unchanged.
"""

from django.urls import path

from apps.events.views_series import (
    EventSeriesCancelView,
    EventSeriesCompleteView,
    EventSeriesDetailView,
    EventSeriesExtendView,
    EventSeriesListCreateView,
    EventSeriesOccurrenceListView,
    EventSeriesPublishView,
)
from apps.events.views_series_collaboration import (
    EventSeriesCollaborationInboxView,
    EventSeriesCollaborationRemoveView,
    EventSeriesCollaborationRespondView,
    EventSeriesCollaboratorListView,
)
from apps.events.views_series_image import EventSeriesImageView
from apps.events.views_series_invites import SeriesInviteListView, SeriesInviteRevokeView

patterns = [
    path(
        'makerspaces/<int:makerspace_id>/event-series/',
        EventSeriesListCreateView.as_view(),
        name='admin-event-series-list-create',
    ),
    path(
        'event-series/<int:pk>/',
        EventSeriesDetailView.as_view(),
        name='admin-event-series-detail',
    ),
    path(
        'event-series/<int:pk>/occurrences/',
        EventSeriesOccurrenceListView.as_view(),
        name='admin-event-series-occurrences',
    ),
    path(
        'event-series/<int:pk>/publish/',
        EventSeriesPublishView.as_view(),
        name='admin-event-series-publish',
    ),
    path(
        'event-series/<int:pk>/cancel/',
        EventSeriesCancelView.as_view(),
        name='admin-event-series-cancel',
    ),
    path(
        'event-series/<int:pk>/complete/',
        EventSeriesCompleteView.as_view(),
        name='admin-event-series-complete',
    ),
    path(
        'event-series/<int:pk>/extend/',
        EventSeriesExtendView.as_view(),
        name='admin-event-series-extend',
    ),
    path(
        'event-series/<int:pk>/image',
        EventSeriesImageView.as_view(),
        name='admin-event-series-image',
    ),
    path(
        'event-series/<int:pk>/collaborators/',
        EventSeriesCollaboratorListView.as_view(),
        name='admin-event-series-collaborators',
    ),
    path(
        'event-series-collaborations/<int:pk>/remove/',
        EventSeriesCollaborationRemoveView.as_view(),
        name='admin-event-series-collaboration-remove',
    ),
    path(
        'makerspaces/<int:makerspace_id>/event-series-collaborations/',
        EventSeriesCollaborationInboxView.as_view(),
        name='admin-event-series-collaboration-inbox',
    ),
    path(
        'event-series-collaborations/<int:pk>/respond/',
        EventSeriesCollaborationRespondView.as_view(),
        name='admin-event-series-collaboration-respond',
    ),
    path(
        'event-series/<int:pk>/invites/',
        SeriesInviteListView.as_view(),
        name='admin-event-series-invites',
    ),
    path(
        'event-series-invites/<int:pk>/revoke/',
        SeriesInviteRevokeView.as_view(),
        name='admin-event-series-invite-revoke',
    ),
]

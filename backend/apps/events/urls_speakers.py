"""Phase 2 events routes: speaker identity, ticket/category edit, member drawer history."""

from django.urls import path

from .views_event_history import StaffMemberEventHistoryView
from .views_speakers import (
    EventSpeakerCandidateView, EventSpeakerInviteView, EventSpeakerListView, EventSpeakerRemoveView,
)
from .views_ticketing_edit import EventCategoryDetailView, EventTicketDetailView

urlpatterns = [
    path("events/<int:pk>/speakers/", EventSpeakerListView.as_view(), name="admin-event-speakers"),
    path("events/<int:pk>/speakers/invite/", EventSpeakerInviteView.as_view(), name="admin-event-speaker-invite"),
    path("events/<int:pk>/speaker-candidates/", EventSpeakerCandidateView.as_view(), name="admin-event-speaker-candidates"),
    path("event-speakers/<int:pk>/remove/", EventSpeakerRemoveView.as_view(), name="admin-event-speaker-remove"),
    path("event-ticket-types/<int:pk>/", EventTicketDetailView.as_view(), name="admin-event-ticket-detail"),
    path("makerspaces/<int:makerspace_id>/event-categories/<int:pk>/", EventCategoryDetailView.as_view(),
         name="admin-event-category-detail"),
    path("makerspaces/<int:makerspace_id>/members/<int:user_id>/events/", StaffMemberEventHistoryView.as_view(),
         name="admin-member-event-history"),
]

"""Included below /api/v1/ by the makerspaces URL barrel."""
from django.urls import path
from .public_profile_views import (
    PublicProfileView, PublicProfileActivityView, PublicProfileEventsView, PublicProfileProjectsView,
)
from .profile_contract_views import HandleView, TimelineListView, TimelineDetailView

urlpatterns = [
    path("public/profiles/<str:handle>/", PublicProfileView.as_view(), name="public-profile"),
    path("public/profiles/<str:handle>/activity", PublicProfileActivityView.as_view(), name="public-profile-activity"),
    path("public/profiles/<str:handle>/events", PublicProfileEventsView.as_view(), name="public-profile-events"),
    path("public/profiles/<str:handle>/projects", PublicProfileProjectsView.as_view(), name="public-profile-projects"),
    path("member/makerspaces/<int:makerspace_id>/profile/handle", HandleView.as_view(), name="member-profile-handle"),
    path("member/makerspaces/<int:makerspace_id>/profile/timeline", TimelineListView.as_view(), name="member-profile-timeline"),
    path("member/makerspaces/<int:makerspace_id>/profile/timeline/<int:pk>", TimelineDetailView.as_view(), name="member-profile-timeline-detail"),
]
